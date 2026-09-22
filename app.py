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

# ==================== ПРАВА РОЛЕЙ ====================
ROLE_PERMISSIONS = {
    "starosta": {
        "can_manage_students": True,
        "can_edit_attendance": True,
        "can_manage_tasks": True,
        "can_edit_notes": True,
        "can_export": True,
        "can_view_tasks": True,
        "can_change_password": True  # Только админы могут менять пароль
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
        "can_change_password": False  # Студенты НЕ могут менять пароль
    }
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


# Дефолтные пользователи
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

# Список студентов строго по фото + Егор Середа
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
def export_to_google_sheets(spreadsheet_id, students, attendance, tasks):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        import json
        import os
    except ImportError:
        raise RuntimeError("Установите библиотеки: pip install gspread google-auth")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_content = os.environ.get("CREDS_JSON")
    
    if creds_content:
        creds_data = json.loads(creds_content)
    else:
        if not os.path.exists(CREDS_FILE):
            raise FileNotFoundError("Не найден файл credentials.json и нет переменной CREDS_JSON")
        with open(CREDS_FILE, "r", encoding="utf-8") as f:
            creds_data = json.load(f)

    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
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


# ==================== ГЛАВНЫЙ ЭКРАН ====================
def main_app():
    user = st.session_state.user
    role = user["role"]
    perms = ROLE_PERMISSIONS.get(role, {})
    is_admin = perms.get("can_manage_students", False)
    can_view_tasks = perms.get("can_view_tasks", False)
    can_change_password = perms.get("can_change_password", False)

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
            "kurator": "🔵 Куратор",
            "student": "🟣 Студент"
        }
        st.info(role_names.get(role, role))

        st.divider()
        menu_options = []
        if is_admin:
            menu_options.extend(["👥 Студенты", "📅 Посещаемость"])
        if perms.get("can_manage_tasks", False):
            menu_options.append("📝 Задания")
        if perms.get("can_edit_notes", False):
            menu_options.append("🗒 Заметки")
        if can_view_tasks and "📝 Задания" not in menu_options:
            menu_options.append("📝 Задания")
        
        # Кнопка смены пароля только если разрешено
        if can_change_password:
            menu_options.append("🔑 Сменить пароль")

        menu = st.radio("Меню", menu_options)

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
                    st.success(f"✅ Готово! Ссылка на таблицу: {url}")
                except Exception as e:
                    st.error(f"❌ Ошибка экспорта: {e}")

    # --- Логика вкладок ---
    if menu == "👥 Студенты" and is_admin:
        st.header("👥 Список студентов")
        st.write(f"Всего студентов: {len(students)}")
        st.dataframe(students, use_container_width=True)
        
        if st.button("🔄 Обновить список до дефолтного"):
            students = DEFAULT_STUDENTS.copy()
            save_json(STUDENTS_FILE, students)
            st.rerun()

    elif menu == "📅 Посещаемость" and is_admin:
        st.header("📅 Посещаемость (авто-сетка на 5 дней)")
        
        dates = [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
        
        if not attendance:
            for d in dates:
                attendance[d] = {s: True for s in students}
            save_json(ATTENDANCE_FILE, attendance)

        st.write("Даты для заполнения:")
        st.write(", ".join(dates))

        for date in dates:
            st.subheader(date)
            cols = st.columns(min(len(students), 5))
            for i, student in enumerate(students):
                if len(cols) > i:
                    default_val = attendance.get(date, {}).get(student, True)
                    attendance[date][student] = st.checkbox(student, value=default_val, key=f"{date}_{student}")
            
        if st.button("💾 Сохранить посещаемость", use_container_width=True):
            save_json(ATTENDANCE_FILE, attendance)
            st.success("Посещаемость сохранена!")

    elif menu == "📝 Задания":
        st.header("📝 Задания (Домашка)")
        
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

    elif menu == "🗒 Заметки" and perms.get("can_edit_notes", False):
        st.header("🗒 Общие заметки")
        notes_text = st.text_area("Текст заметки", value=notes_text, height=200)
        if st.button("Сохранить заметку"):
            save_json(NOTES_FILE, notes_text)
            st.success("Заметка сохранена!")

    elif menu == "🔑 Сменить пароль" and can_change_password:
        st.header("🔐 Смена пароля")
        old_pass = st.text_input("Старый пароль", type="password")
        new_pass = st.text_input("Новый пароль", type="password")
        confirm_pass = st.text_input("Подтвердите новый пароль", type="password")
        
        if st.button("Изменить пароль"):
            current_user_data = users.get(user["login"])
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
        # Экран по умолчанию (для студентов или главная)
        st.title("🎓 Панель старосты группы ИС-116")
        st.markdown(f"Привет, {user['name']}! Выбери раздел в меню слева.")
        
        if role == "student":
            st.info("📋 Как студент, вы видите только список заданий. Смена пароля недоступна.")
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
 
