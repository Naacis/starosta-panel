"""
Панель старосты: обновлённый список студентов, скрытые логины/пароли, полные права для 3 ролей.
"""

import streamlit as st
import json
import os
import hashlib
import secrets
import pandas as pd
from datetime import datetime

# ==================== НАСТРОЙКИ ====================
st.set_page_config(
    page_title="Панель старосты",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CREDS_FILE = "credentials.json"

# ==================== ПРАВА РОЛЕЙ ====================
ROLE_PERMISSIONS = {
    "starosta": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
    },
    "zam": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
    },
    "kurator": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
    },
}

# ==================== УТИЛИТЫ ====================
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}\${h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "\$" in stored_hash:
        salt, h = stored_hash.split("\$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return computed.hex() == h
    # Совместимость со старыми голыми SHA256-хешами
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def col_letter(n):
    """Конвертирует номер колонки в буквенный адрес (1 -> A, 27 -> AA)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


DEFAULT_USERS = {
    "starosta": {
        "password": hash_password("starosta123"),
        "role": "starosta",
        "name": "Староста группы"
    },
    "zam": {
        "password": hash_password("zam123"),
        "role": "zam",
        "name": "Заместитель старосты"
    },
    "kurator": {
        "password": hash_password("kurator123"),
        "role": "kurator",
        "name": "Куратор группы"
    }
}

# ОБНОВЛЁННЫЙ СПИСОК СТУДЕНТОВ (31 человек, включая Егора Середу)
DEFAULT_STUDENTS = [
    "Абукаева Дилара Ринатовна",
    "Бакаляров Кирилл Николаевич",
    "Барахоев Тимур Русланович",
    "Беглянин Никита Сергеевич",
    "Борисов Вячеслав Александрович",
    "Будаев Баин Баирович",
    "Вазлина Алиса Константиновна",
    "Власов Андрей Павлович",
    "Восковский Максим Артемович",
    "Галеева Кира Ильнуровна",
    "Галкин Денис Юрьевич",
    "Гаязов Давид Фанисович",
    "Горбачев Савелий Александрович",
    "Диденко Богдан Алексеевич",
    "Ермолаев Олег Владимирович",
    "Игнатьев Павел Александрович",
    "Ким Артем Андреевич",
    "Ковинский Данила Михайлович",
    "Котов Арсений Владимирович",
    "Лагутин Кирилл Антонович",
    "Леонов Григорий Алексеевич",
    "Лядов Ярослав Александрович",
    "Макаренко Андрей Евгеньевич",
    "Марков Максим Дмитриевич",
    "Матшоев Зафар Миразорович",
    "Митрофанов Богдан Алексеевич",
    "Николаева Евангелина Дмитриевна",
    "Пимкина Дарья Викторовна",
    "Плотников Артём Ильич",
    "Порубов Никита Константинович",
    "Середа Егор"  # Новенький, отчество пока неизвестно
]

# ==================== ЭКСПОРТ В GOOGLE SHEETS ====================
def export_to_google_sheets(spreadsheet_id, students, attendance, tasks,
                             creds_path=CREDS_FILE):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise RuntimeError(
            "Библиотеки не установлены. Выполните: "
            "pip install gspread google-auth"
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Файл '{creds_path}' не найден. "
            "Скачайте JSON-ключ сервисного аккаунта и положите рядом с app.py"
        )

    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id)

    # --- Студенты ---
    try:
        ws = sheet.worksheet("Студенты")
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Студенты", rows=200, cols=5)
    ws.update("A1", [["№", "ФИО"]])
    if students:
        ws.update(f"A2:B{len(students)+1}",
                  [[i, s] for i, s in enumerate(students, 1)])

    # --- Посещаемость ---
    last_col = col_letter(max(len(students) + 1, 2))
    try:
        ws2 = sheet.worksheet("Посещаемость")
        ws2.clear()
    except gspread.WorksheetNotFound:
        ws2 = sheet.add_worksheet(title="Посещаемость", rows=500,
                                   cols=max(len(students) + 2, 5))
    ws2.update("A1", [["Дата"] + students])
    if attendance:
        rows = []
        for date, day_data in sorted(attendance.items()):
            rows.append([date] + ["✓" if day_data.get(s, True) else "✗"
                                  for s in students])
        ws2.update(f"A2:{last_col}{len(rows)+1}", rows)

    # --- Задания ---
    try:
        ws3 = sheet.worksheet("Задания")
        ws3.clear()
    except gspread.WorksheetNotFound:
        ws3 = sheet.add_worksheet(title="Задания", rows=200, cols=4)
    ws3.update("A1", [["Задание", "Дедлайн", "Статус"]])
    if tasks:
        rows = [[t["title"], t["deadline"],
                 "Выполнено" if t["done"] else "В работе"] for t in tasks]
        ws3.update(f"A2:C{len(rows)+1}", rows)

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


# ==================== СЕССИЯ ====================
if "user" not in st.session_state:
    st.session_state.user = None

if "show_export" not in st.session_state:
    st.session_state.show_export = False


def login_screen():
    st.markdown("<h1 style='text-align:center'>🎓 Панель старосты</h1>",
                unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray'>Войдите в систему</p>",
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        users = load_json(USERS_FILE, None) or DEFAULT_USERS
        if not os.path.exists(USERS_FILE):
            save_json(USERS_FILE, users)

        login = st.text_input("Логин", key="login_input")
        password = st.text_input("Пароль", type="password", key="pass_input")

        if st.button("🔓 Войти", use_container_width=True):
            user = users.get(login.strip())
            if user and verify_password(password, user["password"]):
                st.session_state.user = {
                    "login": login.strip(),
                    "role": user["role"],
                    "name": user["name"]
                }
                st.rerun()
            else:
                st.error("Неверный логин или пароль")

        # ПОДСКАЗКА С ЛОГИНАМИ И ПАРОЛЯМИ УДАЛЕНА


# ==================== ГЛАВНЫЙ ЭКРАН ====================
def main_app():
    user = st.session_state.user
    role = user["role"]
    perms = ROLE_PERMISSIONS.get(role, {})
    is_admin = perms.get("can_manage_students", False)

    # Загрузка данных
    students = load_json(STUDENTS_FILE, [])
    if not students and not os.path.exists(STUDENTS_FILE):
        students = DEFAULT_STUDENTS.copy()
        save_json(STUDENTS_FILE, students)

    attendance = load_json(ATTENDANCE_FILE, {})
    tasks = load_json(TASKS_FILE, [])
    notes_text = load_json(NOTES_FILE, "")
    users = load_json(USERS_FILE, DEFAULT_USERS)

    # --- Боковая панель ---
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        role_names = {
            "starosta": "🟢 Староста",
            "zam": "🟡 Заместитель",
            "kurator": "🔵 Куратор"
        }
        st.info(role_names.get(role, role))

        st.divider()
        menu = st.radio("Меню", [
            "👥 Студенты",
            "📅 Посещаемость",
            "📝 Задания",
            "🗒 Заметки",
            "🔑 Сменить пароль"
        ])

        if perms.get("can_export", False):
            st.divider()
            if st.button("📤 Экспорт в Google Таблицы",
                         use_container_width=True):
                st.session_state.show_export = True

        st.divider()
        if st.button("🚪 Выйти", use_container_width=True):
            st.session_state.user = None
            st.session_state.show_export = False
            st.rerun()

    # --- Диалог экспорта ---
    if st.session_state.show_export:
        with st.expander("📤 Экспорт в Google Таблицы", expanded=True):
            sid = st.text_input("ID Google Таблицы",
                                placeholder="из URL между /d/ и /edit")
            if st.button("Начать экспорт"):
                try:
                    url = export_to_google_sheets(sid, students, attendance, tasks)
                    st.success(f"✅ Готово! [Открыть таблицу]({url})")
                except Exception as e:
                    st.error(f"Ошибка: {e}")
            if st.button("Закрыть"):
                st.session_state.show_export = False
                st.rerun()

    # ==================== СТРАНИЦА: СТУДЕНТЫ ====================
    if menu == "👥 Студенты":
        st.header("👥 Список группы")

        # Добавление
        if is_admin:
            col1, col2 = st.columns([3, 1])
            with col1:
                new_name = st.text_input("ФИО нового студента",
                                          placeholder="Иванов Иван Иванович")
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Добавить", use_container_width=True):
                    if new_name.strip() and new_name.strip() not in students:
                        students.append(new_name.strip())
                        # Сортировка по алфавиту после добавления
                        students.sort()
                        save_json(STUDENTS_FILE, students)
                        st.rerun()

        # Таблица
        if students:
            df = pd.DataFrame({"№": range(1, len(students) + 1),
                               "ФИО": students})
            st.dataframe(df, use_container_width=True, hide_index=True)

            if is_admin:
                st.divider()

                # Изменение ФИО
                st.subheader("✏️ Изменить ФИО")
                edit_name = st.selectbox("Выберите студента",
                                         ["—"] + students,
                                         key="edit_student_select")
                if edit_name != "—":
                    new_val = st.text_input("Новое ФИО", value=edit_name,
                                            key="edit_student_input")
                    if st.button("💾 Сохранить", type="primary"):
                        if new_val.strip() and new_val.strip() != edit_name:
                            idx = students.index(edit_name)
                            students[idx] = new_val.strip()
                            # Обновляем записи посещаемости
                            for day_data in attendance.values():
                                if edit_name in day_data:
                                    day_data[new_val.strip()] = day_data.pop(edit_name)
                            # Сортировка после изменения
                            students.sort()
                            save_json(STUDENTS_FILE, students)
                            save_json(ATTENDANCE_FILE, attendance)
                            st.success(f"ФИО изменено: {edit_name} → {new_val.strip()}")
                            st.rerun()

                st.divider()

                # Удаление
                st.subheader("🗑 Удалить студента")
                to_del = st.selectbox("Выберите студента для удаления",
                                      ["—"] + students,
                                      key="del_student_select")
                if to_del != "—" and st.button("🗑 Удалить", type="secondary"):
                    students.remove(to_del)
                    for day_data in attendance.values():
                        day_data.pop(to_del, None)
                    save_json(STUDENTS_FILE, students)
                    save_json(ATTENDANCE_FILE, attendance)
                    st.rerun()
        else:
            st.info("Список пуст. Добавьте студентов.")

    # ==================== СТРАНИЦА: ПОСЕЩАЕМОСТЬ ====================
    elif menu == "📅 Посещаемость":
        st.header("📅 Посещаемость")

        if not students:
            st.warning("Сначала добавьте студентов")
        else:
            date = st.date_input("Дата", datetime.now()).strftime("%Y-%m-%d")
            day_data = attendance.get(date, {})

            st.write(f"### Отметка на **{date}**")

            new_day = {}
            cols = st.columns(3)
            for i, s in enumerate(students):
                with cols[i % 3]:
                    val = st.checkbox(s, value=day_data.get(s, True),
                                      key=f"att_{date}_{i}")
                    new_day[s] = val

            if st.button("💾 Сохранить посещаемость", type="primary"):
                attendance[date] = new_day
                save_json(ATTENDANCE_FILE, attendance)
                st.success(f"Сохранено на {date}")

            if attendance:
                st.divider()
                st.subheader("📊 Сводка по датам")
                summary = pd.DataFrame(attendance).T
                summary.index.name = "Дата"
                st.dataframe(summary, use_container_width=True)

    # ==================== СТРАНИЦА: ЗАДАНИЯ ====================
    elif menu == "📝 Задания":
        st.header("📝 Задания группы")

        if is_admin:
            with st.form("add_task"):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    title = st.text_input("Задание")
                with c2:
                    deadline = st.text_input("Дедлайн (ГГГГ-ММ-ДД)",
                                              value=datetime.now().strftime("%Y-%m-%d"))
                with c3:
                    st.write("")
                    st.write("")
                    submit = st.form_submit_button("➕ Добавить")
                if submit and title.strip():
                    try:
                        datetime.strptime(deadline.strip(), "%Y-%m-%d")
                    except ValueError:
                        st.error("Дедлайн должен быть в формате ГГГГ-ММ-ДД")
                    else:
                        tasks.append({"title": title.strip(),
                                      "deadline": deadline.strip(),
                                      "done": False})
                        save_json(TASKS_FILE, tasks)
                        st.rerun()

        if tasks:
            today = datetime.now().strftime("%Y-%m-%d")
            for i, t in enumerate(tasks):
                mark = "✅" if t["done"] else ("⚠️" if t["deadline"] < today else "⏳")
                c1, c2, c3, c4 = st.columns([5, 2, 1, 1])
                with c1:
                    st.write(f"{mark} **{t['title']}**")
                with c2:
                    st.write(f"до {t['deadline']}")
                with c3:
                    if is_admin:
                        label = "↩️" if t["done"] else "✅"
                        if st.button(label, key=f"toggle_{i}"):
                            tasks[i]["done"] = not tasks[i]["done"]
                            save_json(TASKS_FILE, tasks)
                            st.rerun()
                with c4:
                    if is_admin:
                        if st.button("🗑", key=f"del_{i}"):
                            del tasks[i]
                            save_json(TASKS_FILE, tasks)
                            st.rerun()
        else:
            st.info("Заданий пока нет")

    # ==================== СТРАНИЦА: ЗАМЕТКИ ====================
    elif menu == "🗒 Заметки":
        st.header("🗒 Заметки")
        if is_admin:
            text = st.text_area("Заметки", value=notes_text, height=400)
            if st.button("💾 Сохранить", type="primary"):
                save_json(NOTES_FILE, text)
                st.success("Заметки сохранены")
        else:
            st.text_area("Заметки (только чтение)", value=notes_text,
                         height=400, disabled=True)

    # ==================== СТРАНИЦА: СМЕНА ПАРОЛЯ ====================
    elif menu == "🔑 Сменить пароль":
        st.header("🔑 Смена пароля")
        with st.form("change_pass"):
            old = st.text_input("Старый пароль", type="password")
            new = st.text_input("Новый пароль", type="password")
            confirm = st.text_input("Повторите новый", type="password")
            submit = st.form_submit_button("Сохранить")

            if submit:
                if not verify_password(old, users[user["login"]]["password"]):
                    st.error("Старый пароль неверный")
                elif len(new) < 4:
                    st.error("Пароль слишком короткий (минимум 4 символа)")
                elif new != confirm:
                    st.error("Пароли не совпадают")
                else:
                    users[user["login"]]["password"] = hash_password(new)
                    save_json(USERS_FILE, users)
                    st.success("Пароль изменён!")


# ==================== ЗАПУСК ====================
if st.session_state.user is None:
    login_screen()
else:
    main_app()
