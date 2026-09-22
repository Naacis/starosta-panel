import streamlit as st
import json
import os
import hashlib
import secrets
import pandas as pd
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials

# ==================== НАСТРОЙКИ ====================
st.set_page_config(page_title="Панель старосты ИС-116", page_icon="🎓", layout="wide")

WEEK_DAYS = ["понед", "втор", "среда", "чтв", "пятн", "суб"]
SUB_COLS = ["1", "2", "3"]
HOURS_PER_SUB = 2

STATUS_OPTIONS = ["", "П", "Н", "Б", "О"]

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
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def parse_date(s):
    """Аккуратно парсит дату из строки; возвращает date или None."""
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except Exception:
            continue
    return None


# ==================== ЗАДАЧИ ====================
def add_task(tasks, title, subject, deadline, description, priority):
    tasks.append({
        "id": secrets.token_hex(6),
        "title": title.strip(),
        "subject": subject.strip(),
        "deadline": str(deadline),
        "description": description.strip(),
        "priority": priority,
        "done": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return tasks


def delete_task(tasks, task_id):
    return [t for t in tasks if t.get("id") != task_id]


def toggle_task(tasks, task_id):
    for t in tasks:
        if t.get("id") == task_id:
            t["done"] = not t.get("done", False)
    return tasks


def update_task(tasks, task_id, **fields):
    for t in tasks:
        if t.get("id") == task_id:
            t.update(fields)
    return tasks


PRIORITY_OPTIONS = ["🔴 Высокий", "🟡 Средний", "🟢 Низкий"]


# ==================== ЭКСПОРТ ОТЧЁТА ЗА НЕДЕЛЮ ====================
def export_weekly_report_to_sheet(sheet, week_offset, students, attendance):
    today = datetime.now()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=int(week_offset))
    dates_in_week = [
        (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(len(WEEK_DAYS))
    ]

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

    row1 = [""] * TOTAL_COLS
    row1[0] = "Группа ИС-116"
    for i, day in enumerate(WEEK_DAYS):
        row1[2 + i * len(SUB_COLS)] = day
    row1[20] = "Учебная неделя     №"

    row2 = [""] * TOTAL_COLS
    row2[20] = "Всего пропусков (акад.часов)"
    row2[21] = "Из них"
    row2[23] = "Количество опозданий"

    row3 = [""] * TOTAL_COLS
    row3[1] = "ФИО студента"
    row3[21] = "Уважит. Причина"
    row3[22] = "Неуваж. причина"

    ws.update("A1", [row1, row2, row3])

    data_rows = []
    for idx, name in enumerate(students, 1):
        row = [idx, name]
        u_hours = 0
        n_hours = 0
        lates = 0

        for d_str in dates_in_week:
            day_data = attendance.get(d_str, {}).get(name, {}) or {}
            for sub in SUB_COLS:
                status = (day_data.get(sub, "") or "").strip()
                if status == "Н":
                    row.append("Н"); n_hours += HOURS_PER_SUB
                elif status == "Б":
                    row.append("Б"); u_hours += HOURS_PER_SUB
                elif status == "О":
                    row.append("О"); lates += 1
                elif status == "П":
                    row.append("П")
                else:
                    row.append("")

        total_hours = u_hours + n_hours
        row.append(total_hours if total_hours else "")
        row.append(u_hours if u_hours else "")
        row.append(n_hours if n_hours else "")
        row.append(lates if lates else "")
        row.append("")
        data_rows.append(row)

    if data_rows:
        ws.update("A4", data_rows)

    merges = [
        "A1:A3",
        "C1:E1", "F1:H1", "I1:K1", "L1:N1", "O1:Q1", "R1:T1",
        "C2:T3",
        "U1:Y1",
        "U2:U3",
        "V2:W2",
        "X2:Y2",
    ]
    for m in merges:
        try:
            ws.merge_cells(m)
        except Exception:
            pass

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
DEFAULT_TASKS = []


# ==================== ЗАГРУЗКА ДАННЫХ ====================
users = load_data("users", DEFAULT_USERS)
students = load_data("students", DEFAULT_STUDENTS)
attendance = load_data("attendance", DEFAULT_ATTENDANCE)
tasks = load_data("tasks", DEFAULT_TASKS)

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

            st.subheader("📊 Отчёт за неделю (в формате шаблона)")
            st.caption(
                "Создаёт лист **«Посещаемость»** в Google Таблице. "
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
        st.subheader("📝 Домашние задания")

        # ----- Форма добавления (только для staff) -----
        if is_staff:
            with st.expander("➕ Добавить новое задание", expanded=False):
                with st.form("add_task_form", clear_on_submit=True):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        new_title = st.text_input("Название задания *", placeholder="Например: Лабораторная №3")
                    with c2:
                        new_subject = st.text_input("Предмет", placeholder="Например: Программирование")

                    c3, c4 = st.columns([1, 1])
                    with c3:
                        new_deadline = st.date_input("Дедлайн", value=date.today() + timedelta(days=7))
                    with c4:
                        new_priority = st.selectbox("Приоритет", PRIORITY_OPTIONS, index=1)

                    new_desc = st.text_area(
                        "Описание / что сдать",
                        placeholder="Например: отчёт + код на проверку",
                        height=80,
                    )

                    submitted = st.form_submit_button("✅ Добавить задание", type="primary")

                    if submitted:
                        if not new_title.strip():
                            st.error("Название задания не может быть пустым.")
                        else:
                            tasks = add_task(
                                tasks,
                                title=new_title,
                                subject=new_subject,
                                deadline=new_deadline,
                                description=new_desc,
                                priority=new_priority,
                            )
                            save_data("tasks", tasks)
                            st.success(f"✅ Задание «{new_title}» добавлено.")
                            st.rerun()

        # ----- Фильтры -----
        if tasks:
            fcol1, fcol2, fcol3 = st.columns([1, 1, 2])
            with fcol1:
                filter_status = st.selectbox(
                    "Статус",
                    ["Все", "Активные", "Выполненные"],
                    index=0,
                )
            with fcol2:
                subjects_list = sorted({t.get("subject", "") for t in tasks if t.get("subject")})
                filter_subject = st.selectbox(
                    "Предмет", ["Все"] + subjects_list, index=0,
                )
            with fcol3:
                sort_mode = st.radio(
                    "Сортировка",
                    ["По дедлайну", "По приоритету", "По дате создания"],
                    horizontal=True,
                )

            # Применяем фильтры
            filtered = tasks
            if filter_status == "Активные":
                filtered = [t for t in filtered if not t.get("done")]
            elif filter_status == "Выполненные":
                filtered = [t for t in filtered if t.get("done")]
            if filter_subject != "Все":
                filtered = [t for t in filtered if t.get("subject") == filter_subject]

            # Приоритеты для сортировки: Высокий = 0, Средний = 1, Низкий = 2
            prio_order = {p: i for i, p in enumerate(PRIORITY_OPTIONS)}

            if sort_mode == "По дедлайну":
                filtered = sorted(
                    filtered,
                    key=lambda t: (t.get("done", False), parse_date(t.get("deadline")) or date.max),
                )
            elif sort_mode == "По приоритету":
                filtered = sorted(
                    filtered,
                    key=lambda t: (t.get("done", False), prio_order.get(t.get("priority", ""), 99)),
                )
            else:  # По дате создания
                filtered = sorted(
                    filtered,
                    key=lambda t: (t.get("done", False), t.get("created_at", "")),
                    reverse=False,
                )

            # ----- Сводка -----
            total = len(tasks)
            done_cnt = sum(1 for t in tasks if t.get("done"))
            active_cnt = total - done_cnt
            overdue_cnt = 0
            today_d = date.today()
            for t in tasks:
                if t.get("done"):
                    continue
                d = parse_date(t.get("deadline"))
                if d and d < today_d:
                    overdue_cnt += 1

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Всего", total)
            m2.metric("Активные", active_cnt)
            m3.metric("Выполнено", done_cnt)
            m4.metric("Просрочено", overdue_cnt)

            st.divider()

            # ----- Список заданий -----
            if not filtered:
                st.info("По выбранным фильтрам ничего не найдено.")
            else:
                today_d = date.today()
                for t in filtered:
                    tid = t.get("id", "")
                    is_done = t.get("done", False)
                    deadline_d = parse_date(t.get("deadline"))
                    is_overdue = (not is_done) and deadline_d and deadline_d < today_d
                    is_today = (not is_done) and deadline_d and deadline_d == today_d

                    # Заголовок
                    title_icon = "✅" if is_done else "📌"
                    header = f"{title_icon} **{t.get('title', '—')}**"
                    if t.get("subject"):
                        header += f"  ·  *{t['subject']}*"

                    with st.container(border=True):
                        c1, c2 = st.columns([5, 2])

                        with c1:
                            st.markdown(header)

                            # Дедлайн и приоритет
                            meta_parts = []
                            if t.get("deadline"):
                                dl_txt = f"📅 Дедлайн: **{t['deadline']}**"
                                if is_overdue:
                                    dl_txt += "  🔴 *просрочено*"
                                elif is_today:
                                    dl_txt += "  🟠 *сегодня*"
                                meta_parts.append(dl_txt)
                            if t.get("priority"):
                                meta_parts.append(f"⚡ {t['priority']}")
                            if t.get("created_at"):
                                meta_parts.append(f"🕓 создано {t['created_at']}")
                            if meta_parts:
                                st.markdown("  ·  ".join(meta_parts))

                            if t.get("description"):
                                st.caption(t["description"])

                            status_badge = "✅ Выполнено" if is_done else "⏳ В работе"
                            st.markdown(f"**Статус:** {status_badge}")

                        with c2:
                            if is_staff:
                                # Отметить выполнено / вернуть в работу
                                if st.button(
                                    "↩️ Вернуть" if is_done else "✅ Выполнено",
                                    key=f"toggle_{tid}",
                                    use_container_width=True,
                                ):
                                    tasks = toggle_task(tasks, tid)
                                    save_data("tasks", tasks)
                                    st.rerun()

                                # Редактирование
                                with st.popover("✏️ Редактировать"):
                                    ed_title = st.text_input("Название", value=t.get("title", ""), key=f"ed_t_{tid}")
                                    ed_subj = st.text_input("Предмет", value=t.get("subject", ""), key=f"ed_s_{tid}")
                                    default_deadline = parse_date(t.get("deadline")) or date.today()
                                    ed_deadline = st.date_input("Дедлайн", value=default_deadline, key=f"ed_d_{tid}")
                                    ed_priority = st.selectbox(
                                        "Приоритет",
                                        PRIORITY_OPTIONS,
                                        index=prio_order.get(t.get("priority", ""), 1),
                                        key=f"ed_p_{tid}",
                                    )
                                    ed_desc = st.text_area("Описание", value=t.get("description", ""), key=f"ed_desc_{tid}")

                                    if st.button("💾 Сохранить", key=f"save_{tid}", type="primary"):
                                        tasks = update_task(
                                            tasks, tid,
                                            title=ed_title.strip(),
                                            subject=ed_subj.strip(),
                                            deadline=str(ed_deadline),
                                            priority=ed_priority,
                                            description=ed_desc.strip(),
                                        )
                                        save_data("tasks", tasks)
                                        st.success("Изменения сохранены.")
                                        st.rerun()

                                if st.button("🗑 Удалить", key=f"del_{tid}", use_container_width=True):
                                    tasks = delete_task(tasks, tid)
                                    save_data("tasks", tasks)
                                    st.success("Задание удалено.")
                                    st.rerun()
                            else:
                                # Студент — только чтение
                                st.caption("Просмотр")
        else:
            st.info("📭 Пока нет ни одного задания. Староста может добавить его через форму выше."
                    if is_staff else
                    "📭 Пока нет ни одного задания.")

    # ==================== СТУДЕНТЫ ====================
    with tab3:
        st.write("Управление списком студентов")
        st.json(students)
        if st.button("Сбросить список студентов на дефолтный"):
            save_data("students", DEFAULT_STUDENTS)
            st.rerun() 
