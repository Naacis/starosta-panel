import streamlit as st
import json
import os
import hashlib
import secrets
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ==================== НАСТРОЙКИ ====================
st.set_page_config(page_title="Панель старосты ИС-116", page_icon="🎓", layout="wide")

WEEK_DAYS = ["понед", "втор", "среда", "чтв", "пятн", "суб"]
SUB_COLS = ["1", "2", "3"]
HOURS_PER_SUB = 2  # 1 пара = 2 часа

# ==================== ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ====================
USE_DB = False
ws_data = None
sheet = None

try:
    SPREADSHEET_ID = st.secrets["DATA_SPREADSHEET_ID"]
    CREDS_JSON_STR = st.secrets["CREDS_JSON"]
    
    creds_data = json.loads(CREDS_JSON_STR)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    
    try:
        ws_data = sheet.worksheet("app_data")
    except gspread.exceptions.WorksheetNotFound:
        ws_data = sheet.add_worksheet(title="app_data", rows=100, cols=2)
        ws_data.update("A1:B1", [["key", "value"]])
        
    USE_DB = True
except Exception as e:
    st.error(f"❌ Ошибка подключения к БД: {e}")
    st.info("⚠️ Работа в демо-режиме. Данные сбросятся после перезагрузки.")

# ==================== ФУНКЦИИ ХРАНЕНИЯ ДАННЫХ ====================

def load_data(key, default):
    if USE_DB:
        try:
            cell = ws_data.find(key, in_column=1)
            if cell:
                val = ws_data.cell(cell.row, 2).value
                if val: return json.loads(val)
            return default
        except:
            pass
    
    # Fallback на локальные файлы (если нужно для тестов на ПК)
    path = f"data/{key}.json"
    os.makedirs("data", exist_ok=True)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_data(key, data):
    json_str = json.dumps(data, ensure_ascii=False)
    if USE_DB:
        try:
            cell = ws_data.find(key, in_column=1)
            if cell:
                ws_data.update_cell(cell.row, 2, json_str)
            else:
                ws_data.append_row([key, json_str])
            return True
        except Exception as e:
            st.warning(f"⚠️ Не удалось сохранить в облако: {e}")
            return False
    else:
        path = f"data/{key}.json"
        os.makedirs("data", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return True

# ==================== УТИЛИТЫ ====================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}\${h.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    if "\$" in stored_hash:
        try:
            salt, h = stored_hash.split("\$", 1)
            computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
            return computed.hex() == h
        except:
            return False
    return False

# Данные по умолчанию
DEFAULT_STUDENTS = [
    "Абукаева Дилара Ринатовна", "Бакаляров Кирилл Николаевич", "Барахоев Тимур Русланович",
    "Беглянин Никита Сергеевич", "Борисов Вячеслав Александрович", "Будаев Баин Баирович",
    "Вазлина Алиса Константиновна", "Власов Андрей Павлович", "Восковский Максим Артемович",
    "Галеева Кира Ильнуровна", "Галкин Денис Юрьевич", "Гаязов Давид Фанисович",
    "Горбачев Савелий Александрович", "Диденко Богдан Алексеевич", "Ермолаев Олег Владимирович",
    "Игнатьев Павел Александрович", "Ким Артем Андреевич", "Ковинский Данила Михайлович",
    "Котов Арсений Владимирович", "Лагутин Кирилл Антонович", "Леонов Григорий Алексеевич",
    "Лядов Ярослав Александрович", "Макаренко Андрей Евгеньевич", "Марков Максим Дмитриевич",
    "Матшоев Зафар Миразорович", "Митрофанов Богдан Алексеевич", "Николаева Евангелина Дмитриевна",
    "Пимкина Дарья Викторовна", "Плотников Артём Ильич", "Порубов Никита Константинович", "Середа Егор"
]

DEFAULT_USERS = {
    "starosta": {"password": hash_password("starosta123"), "role": "starosta", "name": "Староста"},
    "zam": {"password": hash_password("zam123"), "role": "zam", "name": "Зам. старосты"},
    "kurator": {"password": hash_password("kurator123"), "role": "kurator", "name": "Куратор"},
    "student_test": {"password": hash_password("student123"), "role": "student", "name": "Студент"}
}

# Структура attendance: { "YYYY-MM-DD": { "ФИО": { "1": "П", "2": "Н", "3": "" } } }
DEFAULT_ATTENDANCE = {}

# ==================== ЛОГИКА ПРИЛОЖЕНИЯ ====================

users = load_data("users", DEFAULT_USERS)
students = load_data("students", DEFAULT_STUDENTS)
attendance = load_data("attendance", DEFAULT_ATTENDANCE)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# --- АВТОРИЗАЦИЯ ---
if not st.session_state.logged_in:
    st.title("Вход в панель старосты")
    login = st.text_input("Логин")
    pwd = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        if login in users and verify_password(pwd, users[login]["password"]):
            st.session_state.logged_in = True
            st.session_state.user = users[login]
            st.rerun()
        else:
            st.error("Неверный логин или пароль")
else:
    user = st.session_state.user
    st.sidebar.title(f"Привет, {user['name']}")
    st.sidebar.write(f"Роль: {user['role']}")
    if st.sidebar.button("Выйти"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("Панель управления посещаемостью (ИС-116)")
    
    tab1, tab2, tab3 = st.tabs(["📋 Посещаемость", "📝 Задачи", "👥 Студенты"])

    with tab1:
        st.subheader("Журнал посещаемости")
        
        # Выбор даты
        selected_date = st.date_input("Выберите дату для отметки", datetime.now())
        date_str = selected_date.strftime("%Y-%m-%d")
        
        # Инициализация данных за дату
        if date_str not in attendance:
            attendance[date_str] = {name: {sub: "" for sub in SUB_COLS} for name in students}
            save_data("attendance", attendance)

        # --- ИНТЕРФЕЙС ОТМЕТКИ ПО ПАРАМ ---
        st.write("### Отметьте посещаемость по парам:")
        
        # Группируем студентов по колонкам для компактности
        cols_per_row = 2
        num_cols = len(students) // cols_per_row + (1 if len(students) % cols_per_row else 0)
        cols = st.columns(cols_per_row)
        
        for i, name in enumerate(students):
            with cols[i % cols_per_row]:
                st.write(f"**{name}**")
                for sub in SUB_COLS:
                    current_val = attendance[date_str][name].get(sub, "")
                    # Варианты: П (Присутствовал), Н (Нет), Б (Болен)
                    new_val = st.selectbox(
                        f"Пара {sub}", 
                        ["", "П", "Н", "Б"], 
                        index=(["", "П", "Н", "Б"].index(current_val) if current_val in ["", "П", "Н", "Б"] else 0),
                        key=f"{name}_{sub}_{date_str}"
                    )
                    attendance[date_str][name][sub] = new_val
        
        if st.button("💾 Сохранить изменения посещаемости", type="primary"):
            save_data("attendance", attendance)
            st.success("Данные сохранены в Google Sheets!")

        st.divider()

        # --- ЭКСПОРТ ОТЧЁТА С ПОДСЧЁТОМ ЧАСОВ ---
        st.subheader("📊 Сформировать отчёт за неделю (с подсчётом часов)")
        
        if st.button("🚀 Создать отчёт в Google Таблице"):
            with st.spinner("Генерация отчёта..."):
                # 1. Определяем диапазон дат (текущая неделя)
                today = datetime.now()
                start_of_week = today - timedelta(days=today.weekday()) # Понедельник
                dates_in_week = [(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
                
                report_data = 
                
                for idx, name in enumerate(students, 1):
                    row = {
                        "№": idx,
                        "ФИО студента": name,
                        "Всего пропущено часов": 0,
                        "Уважительные причины": "",
                        "Неуважительные причины": ""
                    }
                    
                    # Добавляем колонки для каждой пары каждого дня
                    for day in WEEK_DAYS:
                        for sub in SUB_COLS:
                            col_name = f"{day}_{sub}"
                            row[col_name] = "" # Заглушка, заполним ниже
                    
                    # Заполняем данные и считаем часы
                    missed_hours = 0
                    reasons_u = 
                    reasons_n = 
                    
                    for d_str in dates_in_week:
                        if d_str in attendance:
                            student_data = attendance[d_str].get(name, {})
                            for sub in SUB_COLS:
                                status = student_data.get(sub, "")
                                col_key = f"{WEEK_DAYS[datetime.strptime(d_str, '%Y-%m-%d').weekday()]}_{sub}"
                                
                                if status == "Н":
                                    row[col_key] = "Н"
                                    missed_hours += HOURS_PER_SUB
                                    reasons_n.append(f"{d_str} пара {sub}")
                                elif status == "Б":
                                    row[col_key] = "Б"
                                    # Болезнь обычно считается уважительной, но часы тоже теряются
                                    missed_hours += HOURS_PER_SUB
                                    reasons_u.append(f"{d_str} пара {sub} (Болен)")
                                elif status == "П":
                                    row[col_key] = "П"
                                else:
                                    row[col_key] = "-"
                    
                    row["Всего пропущено часов"] = missed_hours
                    row["Уважительные причины"] = "; ".join(reasons_u)
                    row["Неуважительные причины"] = "; ".join(reasons_n)
                    
                    report_data.append(row)

                df_report = pd.DataFrame(report_data)
                
                # Переупорядочиваем колонки для красивого вида (как на фото)
                # Сначала №, ФИО, потом дни недели блоками, потом итоги
                final_columns = ["№", "ФИО студента"]
                for day in WEEK_DAYS:
                    for sub in SUB_COLS:
                        final_columns.append(f"{day}_{sub}")
                final_columns.extend(["Всего пропущено часов", "Уважительные причины", "Неуважительные причины"])
                
                df_report = df_report[final_columns]

                # 2. Запись в Google Sheets
                try:
                    try:
                        ws_report = sheet.worksheet("Отчет_Неделя")
                        ws_report.clear()
                    except:
                        ws_report = sheet.add_worksheet(title="Отчет_Неделя", rows=100, cols=30)
                    
                    # Записываем данные
                    ws_report.update([df_report.columns.values.tolist()] + df_report.values.tolist())
                    
                    # Форматирование: объединение ячеек дней недели
                    def col_letter(n):
                        result = ""
                        while n > 0:
                            n, rem = divmod(n - 1, 26)
                            result = chr(65 + rem) + result
                        return result

                    # Заголовки дней недели начинаются с колонки C (индекс 3, т.к. A=1, B=2)
                    # Но в DataFrame колонки идут подряд. Нужно сопоставить индексы.
                    # В нашем DF: 0=№, 1=ФИО, 2=понед_1, 3=понед_2, 4=понед_3...
                    
                    start_col_idx = 2 # Индекс колонки 'понед_1' в списке колонок
                    
                    for day in WEEK_DAYS:
                        # Вычисляем буквы колонок для объединения
                        c1 = col_letter(start_col_idx + 1) # +1 т.к. col_letter принимает 1-based индекс
                        c2 = col_letter(start_col_idx + 3)
                        range_str = f"{c1}1:{c2}1"
                        
                        ws_report.merge_cells(range_str)
                        ws_report.update_acell(range_str.split(":"), day)
                        
                        start_col_idx += 3
                    
                    # Заголовок "Учебная неделя №" (ставим в последнюю колонку перед итогами)
                    last_data_col = 2 + (len(WEEK_DAYS) * len(SUB_COLS))
                    last_col_letter = col_letter(last_data_col + 1)
                    ws_report.merge_cells(f"{last_col_letter}1:{last_col_letter}3")
                    ws_report.update_acell(f"{last_col_letter}1", "Учебная неделя №")
                    
                    # Жирный шрифт для заголовков
                    ws_report.format("A1:ZZ1", {"textFormat": {"bold": True}})
                    
                    st.success("✅ Отчёт создан на листе 'Отчет_Неделя'!")
                    st.info("Откройте Google Таблицу и проверьте лист 'Отчет_Неделя'. Там есть подсчёт часов и причины.")
                    
                except Exception as e:
                    st.error(f"Ошибка при экспорте: {e}")

    with tab2:
        st.write("Раздел задач (заглушка)")
        st.json(load_data("tasks", {}))

    with tab3:
        st.write("Управление списком студентов")
        st.json(students)
        if st.button("Сбросить список студентов на дефолтный"):
            save_data("students", DEFAULT_STUDENTS)
            st.rerun()
