import streamlit as st
import pandas as pd
import os
from io import BytesIO

# --- Настройки ---
DATA_DIR = "uploaded_files"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Функции ---

@st.cache_data
def load_data_from_excel(file):
    """Загружает и кэширует данные из Excel файла."""
    df = pd.read_excel(file)
    df = df.dropna(how='all').reset_index(drop=True)
    
    data = []
    current_group = None
    for index, row in df.iterrows():
        is_group_header = (pd.isna(row.get('price')) or row.get('price') == '') and pd.notna(row.get('title')) and row.get('title') != ''
        is_analysis_row = pd.notna(row.get('price')) and row.get('price') != '' and pd.notna(row.get('title')) and row.get('title') != ''
        
        if is_group_header:
            current_group = row['title']
        elif is_analysis_row:
            try:
                price_value = float(row['price'])
            except (ValueError, TypeError):
                price_value = 0.0
            
            data.append({
                'original_index': index,
                'group': current_group,
                'title': row['title'],
                'price': price_value,
                'org': row.get('org', ''),
                'time': row.get('time', '')
            })
    return pd.DataFrame(data)

def save_uploaded_file(uploaded_file):
    """Сохраняет загруженный файл на диск."""
    file_path = os.path.join(DATA_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def save_changes_to_file(file_path, df_to_save):
    """Обновляет цены, сохраняет файл и возвращает его содержимое в байтах для скачивания."""
    try:
        with pd.ExcelFile(file_path) as xls:
            all_sheets = {sheet_name: pd.read_excel(xls, sheet_name=sheet_name, header=None) for sheet_name in xls.sheet_names}
        
        sheet_name = list(all_sheets.keys())[0]
        df_sheet = all_sheets[sheet_name]

        title_col_index = 0
        price_col_index = 2
        
        price_map = {row['title']: row['price'] for _, row in df_to_save.iterrows()}

        for index, row in df_sheet.iterrows():
            title = row.get(title_col_index)
            if title in price_map:
                df_sheet.iat[index, price_col_index] = price_map[title]

        # Создаем байтовый поток в памяти для скачивания
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet, index=False, header=False)
        
        # Сохраняем файл на диск
        with open(file_path, 'wb') as f:
            f.write(output.getvalue())
            
        return output.getvalue()
    except Exception as e:
        st.error(f"Ошибка при сохранении файла: {e}")
        return None

def display_analysis_row(row, file_name, is_edit_mode):
    """Отображает одну строку анализа (чекбокс, название, цена)."""
    global_index = row.name
    
    cols = st.columns([8, 2])
    with cols[0]:
        checkbox_key = f"{file_name}_select_{global_index}"
        is_checked = global_index in st.session_state.selected_analyses.get(file_name, [])
        
        if st.checkbox(row['title'], value=is_checked, key=checkbox_key):
            if not is_checked:
                st.session_state.selected_analyses[file_name].append(global_index)
        else:
            if is_checked:
                st.session_state.selected_analyses[file_name].remove(global_index)

    with cols[1]:
        price_key = f"{file_name}_price_{global_index}"
        current_price = float(row['price'])
        
        if is_edit_mode:
            new_price = st.number_input(
                "Цена", 
                value=current_price, 
                key=price_key, 
                step=10.0, 
                format="%.2f", 
                label_visibility="collapsed"
            )
            if new_price != current_price:
                st.session_state.files[file_name]['data'].at[global_index, 'price'] = new_price
        else:
            display_price = f"{int(current_price)}" if current_price == int(current_price) else f"{current_price:.2f}"
            st.markdown(f"<p style='text-align: right; font-weight: bold;'>{display_price} сом</p>", unsafe_allow_html=True)

# --- Инициализация состояния сессии ---
# ... (весь блок инициализации session_state остается без изменений)
if 'files' not in st.session_state:
    st.session_state.files = {}
if 'selected_analyses' not in st.session_state:
    st.session_state.selected_analyses = {}
if 'price_edit_enabled' not in st.session_state:
    st.session_state.price_edit_enabled = {}


# --- Стили (темная тема) ---
# ... (блок стилей остается без изменений)
st.markdown("""
<style>
.stApp {background-color: #121212; color: #ffffff;}
#search-container {position: fixed; top: 0; left: 0; width: 100%; background-color: #1f1f1f; padding: 10px; z-index: 1001; box-shadow: 0 2px 4px rgba(0,0,0,0.2);}
.main-content {margin-top: 70px;}
</style>
""", unsafe_allow_html=True)

# --- UI ---
st.set_page_config(page_title="Калькулятор анализов", layout="wide")

# --- Фиксированный поиск ---
st.markdown('<div id="search-container">', unsafe_allow_html=True)
search_term = st.text_input("🔍 Поиск по анализам", key="global_search", label_visibility="collapsed", placeholder="🔍 Поиск по анализам")
st.markdown('</div>', unsafe_allow_html=True)

# --- Основной контент ---
st.markdown('<div class="main-content">', unsafe_allow_html=True)
st.title("Калькулятор анализов")

# --- Боковая панель для загрузки файлов ---
# ... (блок боковой панели остается без изменений)
with st.sidebar:
    st.header("Импорт файлов")
    uploaded_files = st.file_uploader("Выберите .xlsx файлы", type="xlsx", accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.files:
                file_path = save_uploaded_file(uploaded_file)
                try:
                    df = load_data_from_excel(uploaded_file)
                    st.session_state.files[uploaded_file.name] = {'data': df, 'path': file_path}
                    st.session_state.selected_analyses[uploaded_file.name] = []
                    st.session_state.price_edit_enabled[uploaded_file.name] = False
                    st.success(f"Файл {uploaded_file.name} успешно загружен!")
                except Exception as e:
                    st.error(f"Ошибка при обработке файла {uploaded_file.name}: {e}")
    
    for fname in os.listdir(DATA_DIR):
        if fname.endswith('.xlsx') and fname not in st.session_state.files:
            file_path = os.path.join(DATA_DIR, fname)
            try:
                with open(file_path, "rb") as f:
                    df = load_data_from_excel(BytesIO(f.read()))
                st.session_state.files[fname] = {'data': df, 'path': file_path}
                if fname not in st.session_state.selected_analyses:
                    st.session_state.selected_analyses[fname] = []
                if fname not in st.session_state.price_edit_enabled:
                    st.session_state.price_edit_enabled[fname] = False
            except Exception as e:
                st.error(f"Ошибка автозагрузки файла {fname}: {e}")


# --- Основная область с вкладками ---
if not st.session_state.files:
    st.info("Пожалуйста, импортируйте Excel файлы в боковой панели.")
else:
    tab_names = list(st.session_state.files.keys())
    tabs = st.tabs(tab_names)
    
    total_sum = 0.0

    for i, file_name in enumerate(tab_names):
        with tabs[i]:
            if file_name not in st.session_state.files:
                continue

            file_info = st.session_state.files[file_name]
            df = file_info['data']
            
            # --- Панель управления для вкладки ---
            cols_manage = st.columns([3, 2])
            with cols_manage[0]:
                 is_edit_mode = st.toggle(
                    "Разрешить редактирование цен", 
                    value=st.session_state.price_edit_enabled.get(file_name, False),
                    key=f"price_edit_switch_{file_name}"
                )
                 st.session_state.price_edit_enabled[file_name] = is_edit_mode
            
            with cols_manage[1]:
                if is_edit_mode:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Сохранить", key=f"save_btn_{file_name}"):
                            file_bytes = save_changes_to_file(file_info['path'], df)
                            if file_bytes:
                                st.session_state[f'download_data_{file_name}'] = {
                                    "bytes": file_bytes,
                                    "name": f"updated_{file_name}"
                                }
                                st.success("Сохранено!")
                                load_data_from_excel.clear()
                                if file_name in st.session_state.files:
                                    del st.session_state.files[file_name]
                                st.rerun()
                            else:
                                st.error("Ошибка сохранения.")
                    
                    with col2:
                        download_info = st.session_state.get(f'download_data_{file_name}')
                        if download_info:
                            st.download_button(
                                label=f"📥 Скачать",
                                data=download_info['bytes'],
                                file_name=download_info['name'],
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                key=f'download_btn_{file_name}'
                            )
            
            # --- Фильтрация и отображение ---
            # ... (этот блок остается без изменений)
            filtered_df = df
            if search_term:
                filtered_df = df[df['title'].str.contains(search_term, case=False, na=False)]
            
            if filtered_df.empty:
                st.info("По вашему запросу ничего не найдено.")
                continue

            grouped = filtered_df.groupby('group', dropna=False)
            for group_name, group_df in grouped:
                group_title = group_name if pd.notna(group_name) and group_name else "Без категории"
                
                with st.expander(group_title, expanded=bool(search_term)):
                    for _, row in group_df.iterrows():
                        display_analysis_row(row, file_name, is_edit_mode)

            selected_indices = st.session_state.selected_analyses.get(file_name, [])
            if selected_indices:
                total_sum += df.loc[selected_indices, 'price'].sum()

# --- Плашка с итоговой суммой и кнопками управления ---
# ... (этот блок остается без изменений)
st.markdown("---")
if st.session_state.files:
    cols_bottom = st.columns([1, 1, 3])
    with cols_bottom[0]:
        if st.button("📋 Просмотреть выбранное"):
            has_selection = any(st.session_state.selected_analyses.values())
            if not has_selection:
                st.info("Нет выбранных анализов.")
            else:
                st.subheader("Выбранные анализы:")
                for file_name, indices in st.session_state.selected_analyses.items():
                    if indices and file_name in st.session_state.files:
                        st.write(f"**Файл: {file_name}**")
                        df_file = st.session_state.files[file_name]['data']
                        selected_df = df_file.loc[indices]
                        for _, row in selected_df.iterrows():
                            st.markdown(f"- {row['title']} ({row['price']:.2f} сом)")
    with cols_bottom[1]:
        if st.button("🗑️ Очистить все", key="clear_all_tabs_button"):
            for file_name in st.session_state.selected_analyses:
                st.session_state.selected_analyses[file_name] = []
            st.rerun()

total_sum_placeholder = st.empty()
total_sum_placeholder.markdown(
    f"""
    <div style="position: fixed; bottom: 10px; right: 10px; background-color: #3f51b5; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);">
        <h3 style="margin: 0; color: #ffffff;">Итого: {total_sum:,.2f} сом</h3>
    </div>
    """, 
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)