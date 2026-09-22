import streamlit as st
import json
import os
import hashlib
import secrets
import pandas as pd
from datetime import datetime, timedelta

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

WEEK_DAYS = ["понед", "втор", "среда", "чтв", "пятн", "суб"]
SUB_COLS = ["1", "2", "3"]

# Роли, которым разрешено отмечать посещаемость
ATTENDANCE_ROLES = ("starosta", "zam", "kurator")

# Логины, которым запрещено менять пароль (жёсткий блок)
PASSWORD_CHANGE_BLOCKED_LOGINS = {"student_test"}
PASSWORD_CHANGE_BLOCKED_ROLES = {"student"}

# ==================== ПРАВА РОЛЕЙ ====================
ROLE_PERMISSIONS = {
    "starosta": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
        "can_view_tasks": True,
        "can_change_password": True
    },
    "zam": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
        "can_view_tasks": True,
        "can_change_password": True
    },
    "kurator": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
        "can_view_tasks": True,
        "can_change_password": True
    },
    "student": {
        "can_manage_students": False,
        "can_edit_attendance": False,
        "can_manage_tasks": False,
        "can_edit_notes": False,
        "can_export": False,
        "can_view_tasks": True,
        "can_change_password": False
    }
}

# ==================== УТИЛИТЫ ====================
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" in stored_hash:
        try:
            salt, h = stored_hash.split("$", 1)
            computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
            return computed.hex() == h
        except Exception:
            return False
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
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


# --- Права, вычисляемые для конкретного пользователя ---
def compute_permissions(user):
    """Возвращает словарь эффективных прав для пользователя с учётом роли и логина."""
    role = user.get("role", "")
    login = user.get("login", "")
    perms = dict(ROLE_PERMISSIONS.get(role, {}))

    # Жёсткий блок смены пароля
    if role in PASSWORD_CHANGE_BLOCKED_ROLES or login in PASSWORD_CHANGE_BLOCKED_LOGINS:
        perms["can_change_password"] = False

    # Отмечать посещаемость могут только явно разрешённые роли
    if role not in ATTENDANCE_ROLES:
        perms["can_edit_attendance"] = False

    return perms


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
    },
    "student_test": {
        "password": hash_password("student123"),
        "role": "student",
        "name": "Студент (тестовый)"
    }
}

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
    "Середа Егор"
]


# ==================== ЭКСПОРТ В GOOGLE SHEETS ====================
def build_attendance_header(students_count):
    row1 = ["Группа ИС-116", ""]
    for day in WEEK_DAYS:
        row1.append(day)
        row1.extend([""] * (len(SUB_COLS) - 1))
    row1.append("Учебная неделя №")

    row2 = ["", ""] + ["" for _ in range(len(WEEK_DAYS) * len(SUB_COLS))] + [""]

    row3 = ["№", "ФИО"]
    for _ in WEEK_DAYS:
        for sub in SUB_COLS:
            row3.append(sub)
    row3.append("")

    merges = ["A1:B2"]
    start_col = 3
    for _ in WEEK_DAYS:
        end_col = start_col + len(SUB_COLS) - 1
        merges.append(f"{col_letter(start_col)}1:{col_letter(end_col)}1")
        start_col = end_col + 1
    last_col = 3 + len(WEEK_DAYS) * len(SUB_COLS)
    merges.append(f"{col_letter(last_col)}1:{col_letter(last_col)}3")

    return [row1, row2, row3], merges


def export_to_google_sheets(spreadsheet_id, students, attendance, tasks):
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_content = os.environ.get("CREDS_JSON")

        if not creds_content:
            if os.path.exists(CREDS_FILE):
                with open(CREDS_FILE, "r", encoding="utf-8") as f:
                    creds_data = json.load(f)
            else:
                raise FileNotFoundError("Не найден ключ доступа. Проверьте Secrets в Streamlit Cloud.")
        else:
            try:
                creds_data = json.loads(creds_content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Ошибка формата ключа в Secrets: {e}")

        creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
        client = gspread.authorize(creds)

        try:
            sheet = client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            raise FileNotFoundError(
                f"Таблица с ID '{spreadsheet_id}' не найдена. Проверьте ID и права доступа."
            )
        except gspread.exceptions.APIError as e:
            raise PermissionError(
                f"Нет доступа к таблице. Добавьте email сервисного аккаунта "
                f"в настройки доступа таблицы как 'Редактор'. Детали: {e}"
            )

        # --- Студенты ---
        try:
            ws = sheet.worksheet("Студенты")
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(title="Студенты", rows=200, cols=5)

        ws.update("A1", [["№", "ФИО"]])
        if students:
            data_students = [[i, s] for i, s in enumerate(students, 1)]
            ws.update(f"A2:B{len(students) + 1}", data_students)

        # --- Посещаемость ---
        total_cols = 2 + len(WEEK_DAYS) * len(SUB_COLS) + 1
        try:
            ws2 = sheet.worksheet("Посещаемость")
            ws2.clear()
            try:
                ws2.unmerge_cells(ws2.range(1, 1, 5, total_cols))
            except Exception:
                pass
        except gspread.WorksheetNotFound:
            ws2 = sheet.add_worksheet(
                title="Посещаемость",
                rows=max(len(students) + 20, 100),
                cols=max(total_cols, 10)
            )

        header_rows, merges = build_attendance_header(len(students))
        ws2.update("A1", header_rows)

        for m in merges:
            try:
                ws2.merge_cells(m)
            except Exception:
                pass

        if students:
            rows = []
            sorted_dates = sorted(attendance.keys()) if attendance else []
            for idx, date in enumerate(sorted_dates):
                day_data = attendance[date]
                row = [idx + 1, date]
                for _ in WEEK_DAYS:
                    for j, _sub in enumerate(SUB_COLS):
                        if j == 0:
                            present_count = sum(
                                1 for s in students if day_data.get(s, True)
                            )
                            row.append(f"✓{present_count}/{len(students)}")
                        else:
                            row.append("")
                row.append("")
                rows.append(row)

            if rows:
                last_col = col_letter(total_cols)
                ws2.update(f"A4:{last_col}{3 + len(rows)}", rows)

        # --- Задания ---
        try:
            ws3 = sheet.worksheet("Задания")
            ws3.clear()
        except gspread.WorksheetNotFound:
            ws3 = sheet.add_worksheet(title="Задания", rows=200, cols=4)

        ws3.update("A1", [["Задание", "Дедлайн", "Статус"]])
        if tasks:
            rows_tasks = [
                [t["title"], t["deadline"], "Выполнено" if t["done"] else "В работе"]
                for t in tasks
            ]
            ws3.update(f"A2:C{len(rows_tasks) + 1}", rows_tasks)

        return f"✅ Успешно! Ссылка: https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    except Exception as e:
        return f"❌ Ошибка экспорта: {str(e)}"


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


# ==================== ГЛАВНЫЙ ЭКРАН ====================
def main_app():
    user = st.session_state.user
    role = user["role"]
    login = user["login"]

    # Эффективные права с учётом жёстких блоков
    perms = compute_permissions(user)

    can_manage_students = perms.get("can_manage_students", False)
    can_edit_attendance = perms.get("can_edit_attendance", False)
    can_manage_tasks = perms.get("can_manage_tasks", False)
    can_edit_notes = perms.get("can_edit_notes", False)
    can_export = perms.get("can_export", False)
    can_view_tasks = perms.get("can_view_tasks", False)
    can_change_password = perms.get("can_change_password", False)

    students = load_json(STUDENTS_FILE, [])
    if not students and not os.path.exists(STUDENTS_FILE):
        students = DEFAULT_STUDENTS.copy()
        save_json(STUDENTS_FILE, students)

    attendance = load_json(ATTENDANCE_FILE, {})
    tasks = load_json(TASKS_FILE, [])
    notes_text = load_json(NOTES_FILE, "")
    users = load_json(USERS_FILE, DEFAULT_USERS)

    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        role_names = {
            "starosta": "🟢 Староста",
            "zam": "🟡 Заместитель",
            "kurator": "🔵 Куратор",
            "student": "🟣 Студент"
        }
        st.info(role_names.get(role, role))

        st.divider()
        menu_options = []
        if can_manage_students:
            menu_options.append("👥 Студенты")
        if can_edit_attendance:
            menu_options.append("📅 Посещаемость")
        if can_manage_tasks:
            menu_options.append("📝 Задания")
        if can_edit_notes:
            menu_options.append("🗒 Заметки")
        if can_view_tasks and "📝 Задания" not in menu_options:
            menu_options.append("📝 Задания")
        if can_change_password:
            menu_options.append("🔑 Сменить пароль")

        if not menu_options:
            menu_options = ["🏠 Главная"]

        menu = st.radio("Меню", menu_options)

        if can_export:
            st.divider()
            if st.button("📤 Экспорт в Google Таблицы",
                         use_container_width=True):
                st.session_state.show_export = True

        st.divider()
        if st.button("🚪 Выйти", use_container_width=True):
            st.session_state.user = None
            st.session_state.show_export = False
            st.rerun()

    if st.session_state.show_export and can_export:
        with st.expander("📤 Экспорт в Google Таблицы", expanded=True):
            sid = st.text_input("ID Google Таблицы",
                                placeholder="Только ID (между /d/ и /edit)")
            if st.button("Начать экспорт", type="primary"):
                with st.spinner("Идёт загрузка данных..."):
                    result = export_to_google_sheets(sid, students, attendance, tasks)

                if result.startswith("✅"):
                    st.success(result)
                else:
                    st.error(result)

    # ===== Студенты =====
    if menu == "👥 Студенты" and can_manage_students:
        st.header("👥 Список студентов")
        st.write(f"Всего студентов: {len(students)}")
        st.dataframe(students, use_container_width=True)

        if st.button("🔄 Обновить список до дефолтного"):
            students = DEFAULT_STUDENTS.copy()
            save_json(STUDENTS_FILE, students)
            st.rerun()

    # ===== Посещаемость (полная неделя, только для starosta/zam/kurator) =====
    elif menu == "📅 Посещаемость" and can_edit_attendance:
        st.header("📅 Посещаемость")
        st.caption(
            f"Отмечать посещаемость могут только: Староста, Зам. старосты, Куратор. "
            f"Ваша роль: **{role_names.get(role, role)}**"
        )

        # Выбор недели (смещение относительно текущей)
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        week_offset = st.number_input(
            "Неделя (0 = текущая, отрицательное — прошлые, положительное — будущие)",
            min_value=-8, max_value=8, value=0, step=1
        )
        monday = monday + timedelta(weeks=int(week_offset))

        # Пн..Сб
        dates = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)]

        st.write(f"**Неделя с {dates[0]} по {dates[-1]}**")

        # Инициализация отсутствующих дат
        changed = False
        for d in dates:
            if d not in attendance:
                attendance[d] = {s: True for s in students}
                changed = True
        if changed:
            save_json(ATTENDANCE_FILE, attendance)

        # Сетка отметок: дни в табах, внутри — чекбоксы по студентам
        tabs = st.tabs([f"{d} ({WEEK_DAYS[i]})" for i, d in enumerate(dates)])

        for i, date in enumerate(dates):
            with tabs[i]:
                st.subheader(f"{date} — {WEEK_DAYS[i].capitalize()}")

                col_a, col_b, col_c = st.columns([1, 1, 1])
                if col_a.button("✅ Отметить всех", key=f"all_{date}"):
                    for s in students:
                        attendance[date][s] = True
                    save_json(ATTENDANCE_FILE, attendance)
                    st.rerun()
                if col_b.button("❌ Снять всех", key=f"none_{date}"):
                    for s in students:
                        attendance[date][s] = False
                    save_json(ATTENDANCE_FILE, attendance)
                    st.rerun()
                if col_c.button("🔄 Инвертировать", key=f"inv_{date}"):
                    for s in students:
                        attendance[date][s] = not attendance[date].get(s, True)
                    save_json(ATTENDANCE_FILE, attendance)
                    st.rerun()

                n_cols = 4
                cols = st.columns(n_cols)
                for idx, student in enumerate(students):
                    default_val = attendance.get(date, {}).get(student, True)
                    with cols[idx % n_cols]:
                        attendance[date][student] = st.checkbox(
                            student, value=default_val,
                            key=f"{date}_{student}"
                        )

        if st.button("💾 Сохранить посещаемость за неделю",
                     use_container_width=True, type="primary"):
            save_json(ATTENDANCE_FILE, attendance)
            st.success("Посещаемость за неделю сохранена!")

    # ===== Задания =====
    elif menu == "📝 Задания":
        st.header("📝 Задания (Домашка)")

        if can_manage_tasks:
            with st.form("add_task"):
                title = st.text_input("Название задания")
                deadline = st.date_input("Дедлайн")
                done = st.checkbox("Выполнено")
                if st.form_submit_button("Добавить задание"):
                    tasks.append({
                        "title": title,
                        "deadline": str(deadline),
                        "done": done
                    })
                    save_json(TASKS_FILE, tasks)
                    st.rerun()

        if tasks:
            df_tasks = pd.DataFrame(tasks)
            st.dataframe(df_tasks, use_container_width=True)
        else:
            st.info("Заданий пока нет")

    # ===== Заметки =====
    elif menu == "🗒 Заметки" and can_edit_notes:
        st.header("🗒 Общие заметки")
        notes_text = st.text_area("Текст заметки", value=notes_text, height=200)
        if st.button("Сохранить заметку"):
            save_json(NOTES_FILE, notes_text)
            st.success("Заметка сохранена!")

    # ===== Смена пароля (с жёстким блоком для student и student_test) =====
    elif menu == "🔑 Сменить пароль" and can_change_password:
        st.header("🔐 Смена пароля")
        old_pass = st.text_input("Старый пароль", type="password")
        new_pass = st.text_input("Новый пароль", type="password")
        confirm_pass = st.text_input("Подтвердите новый пароль", type="password")

        if st.button("Изменить пароль"):
            # Повторная защита на случай обхода UI
            if role in PASSWORD_CHANGE_BLOCKED_ROLES or login in PASSWORD_CHANGE_BLOCKED_LOGINS:
                st.error("Смена пароля для этой учётной записи запрещена администратором.")
            else:
                current_user_data = users.get(login)
                if current_user_data and verify_password(old_pass, current_user_data["password"]):
                    if new_pass == confirm_pass and len(new_pass) >= 4:
                        current_user_data["password"] = hash_password(new_pass)
                        save_json(USERS_FILE, users)
                        st.success("Пароль успешно изменен!")
                    else:
                        st.error("Пароли не совпадают или слишком короткие")
                else:
                    st.error("Неверный старый пароль")

    else:
        # Экран по умолчанию
        st.title("🎓 Панель старосты группы ИС-116")
        st.markdown(f"Привет, {user['name']}! Выбери раздел в меню слева.")

        if role == "student":
            st.info("📋 Как студент, вы видите только список заданий. Смена пароля и отметка посещаемости недоступны.")
            if tasks:
                st.subheader("Ваша домашка:")
                for t in tasks:
                    status = "✅ Выполнено" if t["done"] else "⏳ В работе"
                    st.markdown(f"- **{t['title']}** (Дедлайн: {t['deadline']}) — {status}")
            else:
                st.info("Заданий пока нет.")


# ==================== ЗАПУСК ====================
if st.session_state.user is None:
    login_screen()
else:
    main_app() 
