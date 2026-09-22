import streamlit as st
import json
import os
import hashlib
import secrets
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# ==================== НАСТРОЙКИ ====================
st.set_page_config(page_title="Панель старосты ИС-116", page_icon="🎓", layout="wide")

WEEK_DAYS = ["понед", "втор", "среда", "чтв", "пятн", "суб"]  # 6 дней
SUB_COLS = ["1", "2", "3"]                                    # 3 пары в день
HOURS_PER_SUB = 2                                             # 1 пара = 2 акад. часа

# "" — пусто, П — присутствовал, Н — неуваж., Б — болен (уваж.), О — опоздал
STATUS_OPTIONS = ["", "П", "Н", "Б", "О"]

# Всего колонок A..Y = 25:
#   A           — №
#   B           — ФИО
#   C..T (18)   — 6 дней × 3 пары
#   U           — Всего пропусков (акад. часов)
#   V           — Уважит. причина (часы)
#   W           — Неуваж. причина (часы)
#   X           — Количество опозданий
#   Y           — подпись старосты и классного руководителя
TOTAL_COLS = 2 + len(WEEK_DAYS) * len(SUB_COLS) + 5  # = 25


# ==================== ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ====================
USE_DB = False
ws_data = None
sheet = None

try:
    SPREADSHEET_ID = st.secrets["DATA_SPREADSHEET_ID"]
    CREDS_JSON_STR = st.secrets["CREDS_JSON"]

    creds_data = json.loads(CREDS_JSON_STR)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
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


# ==================== ХРАНЕНИЕ ====================
def load_data(key, default):
    if USE_DB:
        try:
            cell = ws_data.find(key, in_column=1)
            if cell:
                val = ws_data.cell(cell.row, 2).value
                if val:
                    return json.loads(val)
            return default
        except Exception:
            pass

    path = f"data/{key}.json"
    os.makedirs("data", exist_ok=True)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
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
    return f"{salt}${h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" in stored_hash:
        try:
            salt, h = stored_hash.split("$", 1)
            computed = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), 100_000
            )
            return computed.hex() == h
        except Exception:
            return False
    return False


def col_letter(n):
    """1 -> A, 2 -> B, ..., 27 -> AA."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


# ==================== ЭКСПОРТ ОТЧЁТА ЗА НЕДЕЛЮ ====================
def export_weekly_report_to_sheet(sheet, week_offset, students, attendance):
    """
    Экспортирует отчёт за неделю в лист «Посещаемость» — структура 1:1 как в шаблоне.

      A              B                 C D E   F G H   I J K   L M N   O P Q   R S T   U             V         W           X          Y
    1 Группа ИС-116                   [понед]  [втор]  [среда] [чтв]   [пятн]  [суб]   Учебная неделя №
    2                                [           — пусто —                 ]          Всего пропусков  Из них   Кол-во опозн.
    3               ФИО студента     [           — пусто —                 ]                   Уваж.   Неуваж.
    4  1  Абукаева Дилара ...        . . .   . . .   Н Н Н   . . .   Н . .   . . .    7       6       1        Староста ______ / Кл.рук.______
    """
    today = datetime.now()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=int(week_offset))
    dates_in_week = [
        (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(len(WEEK_DAYS))
    ]

    # --- Получаем или создаём лист ---
    title = "Посещаемость"
    try:
        ws = sheet.worksheet(title)
        ws.clear()
        try:
            ws.unmerge_cells(ws.range(1, 1, max(len(students) + 10, 60), 30))
        except Exception:
            pass
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(
            title=title,
            rows=max(len(students) + 10, 60),
            cols=30,
        )

    # ---------- ШАПКА (3 строки × 25 колонок A..Y) ----------
    # Индексы (0-based): A=0, B=1, C=2, D=3, ..., T=19, U=20, V=21, W=22, X=23, Y=24

    row1 = [""] * TOTAL_COLS
    row1[0] = "Группа ИС-116"                          # A1
    for i, day in enumerate(WEEK_DAYS):
        row1[2 + i * len(SUB_COLS)] = day              # C1, F1, I1, L1, O1, R1
    row1[20] = "Учебная неделя     №"                  # U1  (merge U1:Y1)

    row2 = [""] * TOTAL_COLS
    row2[20] = "Всего пропусков (акад.часов)"          # U2  (merge U2:U3)
    row2[21] = "Из них"                                # V2  (merge V2:W2)
    row2[23] = "Количество опозданий"                  # X2  (merge X2:Y2)

    row3 = [""] * TOTAL_COLS
    row3[1] = "ФИО студента"                           # B3
    row3[21] = "Уважит. Причина"                       # V3
    row3[22] = "Неуваж. причина"                       # W3

    ws.update("A1", [row1, row2, row3])

    # ---------- ДАННЫЕ СТУДЕНТОВ (начиная с 4-й строки) ----------
    data_rows = []
    for idx, name in enumerate(students, 1):
        row = [idx, name]
        u_hours = 0   # уважительные часы (по метке Б)
        n_hours = 0   # неуважительные часы (по метке Н)
        lates = 0     # количество опозданий (по метке О)

        # 18 колонок отметок: 6 дней × 3 пары
        for d_str in dates_in_week:
            day_data = attendance.get(d_str, {}).get(name, {}) or {}
            for sub in SUB_COLS:
                status = (day_data.get(sub, "") or "").strip()
                if status == "Н":
                    row.append("Н")
                    n_hours += HOURS_PER_SUB
                elif status == "Б":
                    row.append("Б")
                    u_hours += HOURS_PER_SUB
                elif status == "О":
                    row.append("О")
                    lates += 1
                elif status == "П":
                    row.append("П")
                else:
                    row.append("")

        total_hours = u_hours + n_hours
        row.append(total_hours if total_hours else "")   # U — Всего пропусков
        row.append(u_hours if u_hours else "")           # V — Уважит. причина
        row.append(n_hours if n_hours else "")           # W — Неуваж. причина
        row.append(lates if lates else "")               # X — Количество опозданий
        row.append("")                                    # Y — подпись (заполним ниже)
        data_rows.append(row)

    if data_rows:
        ws.update("A4", data_rows)

    # ---------- ОБЪЕДИНЕНИЯ ЯЧЕЕК ----------
    merges = [
        "A1:A3",                                                  # "Группа ИС-116"
        "C1:E1", "F1:H1", "I1:K1", "L1:N1", "O1:Q1", "R1:T1",     # названия дней
        "C2:T3",                                                   # пустая зона под днями
        "U1:Y1",                                                   # "Учебная неделя №"
        "U2:U3",                                                   # "Всего пропусков"
        "V2:W2",                                                   # "Из них"
        "X2:Y2",                                                   # "Количество опозданий"
    ]
    for m in merges:
        try:
            ws.merge_cells(m)
        except Exception:
            pass

    # ---------- Строка для подписей (в колонке Y, объединена по всем студентам) ----------
    if data_rows:
        last_row = 3 + len(data_rows)
        sig_text = (
            "Староста _______________________________________      "
            "Классный руководитель _______________________________________"
        )
        ws.update("Y4", [[sig_text]])
        try:
            ws.merge_cells(f"Y4:Y{last_row}")
        except Exception:
            pass

    # ---------- Форматирование ----------
    try:
        ws.format(
            "A1:Y3",
            {
                "textFormat": {"bold": True},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
        )
        ws.freeze(rows=3)
    except Exception:
        pass

    return dates_in_week


# ==================== ДЕФОЛТНЫЕ ДАННЫЕ ====================
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
    "Пимкина Дарья Викторовна", "Плотников Артём Ильич", "Порубов Никита Константинович", "Середа Егор",
]

DEFAULT_USERS = {
    "starosta": {"password": hash_password("starosta123"), "role": "starosta", "name": "Староста"},
    "zam": {"password": hash_password("zam123"), "role": "zam", "name": "Зам. старосты"},
    "kurator": {"password": hash_password("kurator123"), "role": "kurator", "name": "Куратор"},
    "student_test": {"password": hash_password("student123"), "role": "student", "name": "Студент"},
}

DEFAULT_ATTENDANCE = {}


# ==================== ЗАГРУЗКА ДАННЫХ ====================
users = load_data("users", DEFAULT_USERS)
students = load_data("students", DEFAULT_STUDENTS)
attendance = load_data("attendance", DEFAULT_ATTENDANCE)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None


# ==================== АВТОРИЗАЦИЯ ====================
if not st.session_state.logged_in:
    st.title("Вход в панель старосты")
    login = st.text_input("Логин")
    pwd = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        if login in users and verify_password(pwd, users[login]["password"]):
            st.session_state.logged_in = True
            st.session_state.user = {**users[login], "login": login}
            st.rerun()
        else:
            st.error("Неверный логин или пароль")
else:
    user = st.session_state.user
    role = user["role"]
    is_staff = role in ("starosta", "zam", "kurator")

    st.sidebar.title(f"Привет, {user['name']}")
    st.sidebar.write(f"Роль: {role}")
    if st.sidebar.button("Выйти"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    st.title("Панель управления посещаемостью (ИС-116)")

    tab1, tab2, tab3 = st.tabs(["📋 Посещаемость", "📝 Задачи", "👥 Студенты"])

    # ==================== ПОСЕЩАЕМОСТЬ ====================
    with tab1:
        if not is_staff:
            st.warning("Отмечать посещаемость могут только староста, зам. старосты и куратор.")
        else:
            st.subheader("Журнал посещаемости")

            col_d, col_w = st.columns([2, 3])
            with col_d:
                selected_date = st.date_input("Дата", datetime.now())
            date_str = selected_date.strftime("%Y-%m-%d")

            wd = selected_date.weekday()
            day_name = WEEK_DAYS[wd] if wd < len(WEEK_DAYS) else "воскр"
            with col_w:
                st.info(f"Выбранная дата: **{date_str}** ({day_name})")

            if date_str not in attendance:
                attendance[date_str] = {
                    name: {sub: "" for sub in SUB_COLS} for name in students
                }

            for name in students:
                if name not in attendance[date_str]:
                    attendance[date_str][name] = {sub: "" for sub in SUB_COLS}
                else:
                    for sub in SUB_COLS:
                        attendance[date_str][name].setdefault(sub, "")

            st.write("### Отметьте посещаемость по парам")
            st.caption(
                "**П** — присутствовал, **Н** — нет (неуваж.), "
                "**Б** — болен (уваж.), **О** — опоздал, пусто — не отмечено."
            )

            editor_rows = []
            for name in students:
                row = {"ФИО": name}
                for sub in SUB_COLS:
                    row[f"Пара {sub}"] = attendance[date_str][name].get(sub, "")
                editor_rows.append(row)

            df_editor = pd.DataFrame(editor_rows)

            column_config = {
                "ФИО": st.column_config.TextColumn("ФИО", disabled=True, width="large"),
            }
            for sub in SUB_COLS:
                column_config[f"Пара {sub}"] = st.column_config.SelectboxColumn(
                    f"Пара {sub}",
                    help=f"Отметка за {sub}-ю пару",
                    options=STATUS_OPTIONS,
                    required=False,
                    width="small",
                )

            edited_df = st.data_editor(
                df_editor,
                column_config=column_config,
                hide_index=True,
                use_container_width=True,
                key=f"attendance_editor_{date_str}",
            )

            col_save, col_clear, _ = st.columns([1, 1, 3])
            with col_save:
                if st.button("💾 Сохранить", type="primary", use_container_width=True):
                    for _, row in edited_df.iterrows():
                        name = row["ФИО"]
                        for sub in SUB_COLS:
                            attendance[date_str][name][sub] = row.get(f"Пара {sub}", "") or ""
                    save_data("attendance", attendance)
                    st.success(f"✅ Посещаемость за {date_str} сохранена.")
            with col_clear:
                if st.button("🧹 Очистить день", use_container_width=True):
                    attendance[date_str] = {
                        name: {sub: "" for sub in SUB_COLS} for name in students
                    }
                    save_data("attendance", attendance)
                    st.rerun()

            st.divider()

            # ==================== ОТЧЁТ ЗА НЕДЕЛЮ ====================
            st.subheader("📊 Отчёт за неделю (в формате шаблона)")
            st.caption(
                "Создаёт лист **«Посещаемость»** в Google Таблице. "
                "Структура — точно как в шаблоне: 6 дней × 3 пары; "
                "1 пара = 2 акад. часа; **Н** и **Б** дают +2 часа каждый, **О** — опоздание."
            )

            week_offset = st.number_input(
                "Сдвиг недели (0 = текущая, -1 = прошлая, 1 = следующая)",
                min_value=-8, max_value=8, value=0, step=1,
            )

            if st.button("🚀 Создать отчёт в Google Таблице", type="primary"):
                if not USE_DB or sheet is None:
                    st.error("❌ Нет подключения к Google Sheets. Настройте secrets.")
                else:
                    with st.spinner("Генерация отчёта..."):
                        try:
                            dates = export_weekly_report_to_sheet(
                                sheet=sheet,
                                week_offset=int(week_offset),
                                students=students,
                                attendance=attendance,
                            )
                            st.success("✅ Отчёт создан на листе «Посещаемость»!")
                            st.info(
                                f"Период: **{dates[0]}** — **{dates[-1]}**. "
                                f"Ссылка: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
                            )
                        except Exception as e:
                            st.error(f"Ошибка при экспорте: {e}")

    # ==================== ЗАДАЧИ ====================
    with tab2:
        st.write("Раздел задач (заглушка)")
        st.json(load_data("tasks", {}))

    # ==================== СТУДЕНТЫ ====================
    with tab3:
        st.write("Управление списком студентов")
        st.json(students)
        if st.button("Сбросить список студентов на дефолтный"):
            save_data("students", DEFAULT_STUDENTS)
            st.rerun() 
