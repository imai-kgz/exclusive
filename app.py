import streamlit as st
import pandas as pd
import os
from io import BytesIO
from fpdf import FPDF
import openpyxl

# --- Settings ---
DATA_DIR = "uploaded_files"
os.makedirs(DATA_DIR, exist_ok=True)
# Ensure both font files are in the same folder as the script
FONT_REGULAR_PATH = "JetBrainsMono-Regular.ttf"
FONT_BOLD_PATH = "JetBrainsMono-Bold.ttf"

# --- User Credentials ---
# IMPORTANT: In a real production app, use st.secrets for storing credentials!
# For this example, we are hardcoding them.
VALID_USERNAME = st.secrets["APP_USERNAME"]
VALID_PASSWORD = st.secrets["APP_PASSWORD"]

# --- Session State Initialization ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'
if 'files' not in st.session_state:
    st.session_state.files = {}
if 'selected_analyses' not in st.session_state:
    st.session_state.selected_analyses = {}
if 'price_edit_enabled' not in st.session_state:
    st.session_state.price_edit_enabled = {}
if "show_selected" not in st.session_state:
    st.session_state.show_selected = False
# Add new session state for login status
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- Core Functions ---

@st.cache_data
def load_data_from_excel(file_content):
    """Loads and caches data from an Excel file's content, reading colors."""
    wb = openpyxl.load_workbook(BytesIO(file_content), data_only=True)
    sheet = wb.active
    data = []
    current_group = None

    for row_idx, row in enumerate(sheet.iter_rows(min_row=1, values_only=False), start=1):
        if len(row) < 5:
            continue

        title_cell, color0_cell, color1_cell, price_cell, time_cell = row[:5]
        title = title_cell.value
        price = price_cell.value

        is_group_header = (price is None or price == '') and (title is not None and title != '')
        is_analysis_row = (price is not None and price != '') and (title is not None and title != '')

        if is_group_header:
            current_group = title
        elif is_analysis_row:
            try:
                price_value = float(price)
            except (ValueError, TypeError):
                price_value = 0.0

            color0_color = f"#{color0_cell.fill.fgColor.rgb[2:]}".lower() if color0_cell.fill.patternType == 'solid' and color0_cell.fill.fgColor.rgb and color0_cell.fill.fgColor.rgb not in ('00000000', 'FFFFFFFF') else None
            color1_color = f"#{color1_cell.fill.fgColor.rgb[2:]}".lower() if color1_cell.fill.patternType == 'solid' and color1_cell.fill.fgColor.rgb and color1_cell.fill.fgColor.rgb not in ('00000000', 'FFFFFFFF') else None

            data.append({
                'original_index': row_idx - 1,
                'group': current_group,
                'title': title,
                'price': price_value,
                'color_0_text': str(color0_cell.value or ''),
                'color_0_color': color0_color,
                'color_1_text': str(color1_cell.value or ''),
                'color_1_color': color1_color,
                'time': time_cell.value or ''
            })
    return pd.DataFrame(data)

def save_uploaded_file(uploaded_file):
    """Saves an uploaded file to the disk."""
    file_path = os.path.join(DATA_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def save_changes_to_file(file_path, df_to_save):
    """
    Updates prices in the Excel file, preserving all existing styles (like colors),
    and returns the file's content in bytes.
    """
    try:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        price_map = {row['title']: row['price'] for _, row in df_to_save.iterrows()}

        for row in sheet.iter_rows(min_row=1):
            if len(row) > 3 and row[0].value in price_map and (row[3].value is not None and row[3].value != ''):
                row[3].value = price_map[row[0].value]
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        with open(file_path, 'wb') as f:
            f.write(output.getvalue())
            
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        st.error(f"Ошибка при сохранении файла: {e}")
        return None


def generate_pdf_receipt(selected_analyses_data):
    """Generates a PDF receipt with aligned dots and handles long text."""
    pdf = FPDF()
    pdf.add_page()
    
    try:
        pdf.add_font('DejaVu', '', FONT_REGULAR_PATH, uni=True)
        pdf.add_font('DejaVu', 'B', FONT_BOLD_PATH, uni=True)
    except Exception as e:
        st.error(f"Font Error: {e}. Ensure font files are in the same folder.")
        return None

    pdf.set_font("DejaVu", size=16, style="B")
    pdf.cell(0, 10, txt="Ваш Чек", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("DejaVu", size=11)
    total_sum_pdf = 0
    line_width = 190 

    for item in selected_analyses_data:
        color_texts = ' '.join(filter(None, [item.get('color_0_text'), item.get('color_1_text')])).strip()
        full_title = f"{item['title']} ({color_texts})" if color_texts else item['title']
        
        price = float(item['price'])
        price_str = f"{price:,.2f} с"
        total_sum_pdf += price
        
        price_width = pdf.get_string_width(price_str)
        dot_width = pdf.get_string_width('.')

        lines = []
        remaining_text = full_title
        while pdf.get_string_width(remaining_text) > 0:
            line = remaining_text
            while pdf.get_string_width(line) > line_width:
                line = line[:-1]
            
            if len(line) < len(remaining_text):
                split_pos = line.rfind(' ')
                if split_pos > 0:
                    line = line[:split_pos]
            
            lines.append(line)
            remaining_text = remaining_text[len(line):].strip()

        if not lines:
            continue

        if len(lines) > 1:
            for line in lines[:-1]:
                pdf.cell(0, 8, txt=line, ln=True)
        
        last_line = lines[-1]
        last_line_width = pdf.get_string_width(last_line)

        if last_line_width + price_width < (line_width - 5):
            num_dots = int((line_width - last_line_width - price_width) / dot_width) if dot_width > 0 else 0
            dots = '.' * max(0, num_dots)
            
            pdf.cell(last_line_width, 8, txt=last_line, ln=False)
            pdf.cell(line_width - last_line_width - price_width, 8, txt=dots, ln=False)
            pdf.cell(price_width, 8, txt=price_str, ln=True, align="R")
        else:
            pdf.cell(0, 8, txt=last_line, ln=True)
            
            num_dots = int((line_width - price_width) / dot_width) if dot_width > 0 else 0
            dots = '.' * max(0, num_dots)
            
            pdf.cell(line_width - price_width, 8, txt=dots, ln=False)
            pdf.cell(price_width, 8, txt=price_str, ln=True, align="R")

    pdf.ln(5)
    pdf.set_font("DejaVu", size=14, style="B")
    pdf.cell(150, 10, txt="Итого:", ln=False, align="R")
    pdf.cell(40, 10, txt=f"{total_sum_pdf:,.2f} с", ln=True, align="R")
    
    return pdf.output(dest="S").encode('latin-1')


# --- Helper UI Functions ---

def get_text_color(bg_color):
    """Determines if text should be black or white based on background luminance."""
    if not bg_color or len(bg_color) != 7: return '#000000'
    r, g, b = int(bg_color[1:3], 16), int(bg_color[3:5], 16), int(bg_color[5:7], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return '#000000' if luminance > 0.5 else '#ffffff'

def get_color_display_html(item, col_prefix):
    """Generates HTML for a colored cell display."""
    text = item.get(col_prefix + '_text', '')
    color = item.get(col_prefix + '_color')
    if text:
        text_color = get_text_color(color)
        style = f"background-color:{color}; color:{text_color}; padding:2px 5px; border-radius:3px; font-size:14px;" if color else ""
        return f"<span style='{style}'>{text}</span>"
    if color:
        return f"<div style='background-color:{color}; height:20px; width:100%; border-radius:3px;'></div>"
    return ""

def get_theme_styles(theme='dark'):
    if theme == 'light':
        return """
        <style>
            .stApp { background-color: #FFFFFF; color: #111111; font-size: 17px; }
            .stExpander, .stNumberInput input { background-color: #EEEEEE; }
            .stButton > button { background-color: #4CAF50; color: white; }
            p, label, .stMarkdown, h1, h2, h3 { color: #111111 !important; }
            #search-container { background-color: #FFFFFF; }
            .price-text { color: #000 !important; }
        </style>
        """
    return """
    <style>
        .stApp { background-color: #0E1117; color: #FAFAFA; font-size: 17px; }
        .stExpander, .stNumberInput input { background-color: #262730; }
        .stButton > button { background-color: #3f51b5; color: white; }
        p, label, .stMarkdown, h1, h2, h3 { color: #FAFAFA !important; }
        #search-container { background-color: #0E1117; }
        .price-text { color: #fff !important; }
    </style>
    """

# --- Authorization ---
def login_form():
    """Displays the login form and handles authentication."""
    st.set_page_config(page_title="Авторизация", layout="centered")
    st.markdown(get_theme_styles(st.session_state.theme), unsafe_allow_html=True)
    
    with st.container(border=True):
        st.title("Авторизация")
        st.write("Пожалуйста, войдите, чтобы продолжить.")
        username = st.text_input("Имя пользователя", key="username")
        password = st.text_input("Пароль", type="password", key="password")
        
        if st.button("Войти", type="primary"):
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Неверное имя пользователя или пароль.")

# --- Main Application UI ---
def main_app():
    """The main application interface, shown only after login."""
    st.set_page_config(page_title="Калькулятор анализов", layout="wide")
    st.markdown(get_theme_styles(st.session_state.theme), unsafe_allow_html=True)
    st.markdown("""
    <style>
        #search-container { position: fixed; top: 0; left: 0; width: 100%; padding: 10px 20px; z-index: 1001; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        .main-content { margin-top: 80px; }
        .price-text { text-align: left; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

    # --- Sidebar ---
    with st.sidebar:
        st.header("Настройки")
        is_dark = st.toggle("Темная тема", value=(st.session_state.theme == 'dark'))
        st.session_state.theme = 'dark' if is_dark else 'light'
        
        st.markdown("---")
        st.header("Импорт файлов")
        uploaded_files = st.file_uploader("Выберите .xlsx файлы", type="xlsx", accept_multiple_files=True)

        if uploaded_files:
            for file in uploaded_files:
                if file.name not in st.session_state.files:
                    path = save_uploaded_file(file)
                    df = load_data_from_excel(file.getvalue()) 
                    st.session_state.files[file.name] = {'data': df, 'path': path}
                    st.success(f"Файл {file.name} загружен.")
                    st.rerun()

        # Autoload files from disk
        for fname in os.listdir(DATA_DIR):
            if fname.endswith('.xlsx') and fname not in st.session_state.files:
                path = os.path.join(DATA_DIR, fname)
                with open(path, "rb") as f:
                    df = load_data_from_excel(f.read())
                st.session_state.files[fname] = {'data': df, 'path': path}
        
        st.markdown("---")
        st.header("Управление сессией")
        if st.button("Выйти"):
            st.session_state.logged_in = False
            # Clear sensitive data on logout
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


    # --- Main Content ---
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    st.title("Калькулятор анализов")

    st.markdown('<div id="search-container">', unsafe_allow_html=True)
    search_term = st.text_input("Поиск", placeholder="🔍 Поиск по названию, группе или тексту в ячейке", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    total_sum = 0.0

    if not st.session_state.files:
        st.header("📁 Файлы не загружены")
        st.info("Пожалуйста, импортируйте один или несколько Excel файлов в боковой панели, чтобы начать работу.")
    else:
        tab_names = list(st.session_state.files.keys())
        tabs = st.tabs(tab_names)

        for i, file_name in enumerate(tab_names):
            with tabs[i]:
                if file_name not in st.session_state.files: continue
                
                file_info = st.session_state.files[file_name]
                df = file_info['data']
                
                manage_cols = st.columns([2, 2, 1])
                with manage_cols[0]:
                    is_edit_mode = st.toggle("Редактировать цены", key=f"edit_{file_name}")
                
                if is_edit_mode:
                    with manage_cols[1]:
                        if st.button("💾 Сохранить", key=f"save_{file_name}"):
                            file_bytes = save_changes_to_file(file_info['path'], df)
                            if file_bytes:
                                st.session_state[f'download_{file_name}'] = {"bytes": file_bytes, "name": f"updated_{file_name}"}
                                st.success("Сохранено!")
                                load_data_from_excel.clear()
                                if file_name in st.session_state.files:
                                    del st.session_state.files[file_name]
                                st.rerun()
                            else:
                                st.error("Ошибка сохранения.")

                with manage_cols[2]:
                    if st.button("🗑️ Удалить файл", key=f"delete_{file_name}"):
                        try:
                            os.remove(file_info['path'])
                            for key in list(st.session_state.keys()):
                                if isinstance(st.session_state[key], dict) and file_name in st.session_state[key]:
                                    del st.session_state[key][file_name]
                            load_data_from_excel.clear()
                            st.success(f"Файл {file_name} удален.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Не удалось удалить файл: {e}")

                filtered_df = pd.DataFrame()
                if search_term:
                    search_lower = search_term.lower()
                    item_mask = (
                        df['title'].str.lower().str.contains(search_lower, na=False) |
                        df['color_0_text'].str.lower().str.contains(search_lower, na=False) |
                        df['color_1_text'].str.lower().str.contains(search_lower, na=False)
                    )
                    df['group'] = df['group'].fillna('')
                    matching_groups = df[df['group'].str.lower().str.contains(search_lower, na=False)]['group'].unique()
                    group_mask = df['group'].isin(matching_groups)
                    filtered_df = df[item_mask | group_mask]
                else:
                    filtered_df = df

                if filtered_df.empty:
                    st.info("Ничего не найдено.")
                else:
                    for group_name, group_df in filtered_df.groupby('group', dropna=False):
                        if not group_name or pd.isna(group_name):
                            continue

                        with st.expander(group_name, expanded=bool(search_term)):
                            for idx, row in group_df.iterrows():
                                cols = st.columns([5, 1.5, 1.5, 2])
                                is_checked = idx in st.session_state.selected_analyses.get(file_name, [])
                                
                                if cols[0].checkbox(row['title'], value=is_checked, key=f"check_{file_name}_{idx}"):
                                    if not is_checked:
                                        st.session_state.selected_analyses.setdefault(file_name, []).append(idx)
                                elif is_checked:
                                    st.session_state.selected_analyses[file_name].remove(idx)

                                cols[1].markdown(get_color_display_html(row, 'color_0'), unsafe_allow_html=True)
                                cols[2].markdown(get_color_display_html(row, 'color_1'), unsafe_allow_html=True)

                                with cols[3]:
                                    if is_edit_mode:
                                        new_price = st.number_input("Цена", value=float(row['price']), key=f"price_{file_name}_{idx}", label_visibility="collapsed")
                                        if new_price != row['price']:
                                            st.session_state.files[file_name]['data'].at[idx, 'price'] = new_price
                                    else:
                                        price_str = f"{int(row['price'])}" if row['price'] == int(row['price']) else f"{row['price']:.2f}"
                                        st.markdown(f"<p class='price-text'>{price_str} сом</p>", unsafe_allow_html=True)
                
                selected_indices = st.session_state.selected_analyses.get(file_name, [])
                if selected_indices:
                    valid_indices = [idx for idx in selected_indices if idx in df.index]
                    total_sum += df.loc[valid_indices, 'price'].sum()
        
        st.markdown("---")
        selected_data = []
        for fname, indices in st.session_state.selected_analyses.items():
            if indices and fname in st.session_state.files:
                df_file = st.session_state.files[fname]['data']
                valid_indices = [idx for idx in indices if idx in df_file.index]
                for _, row in df_file.loc[valid_indices].iterrows():
                    selected_data.append(row.to_dict())

        if selected_data:
            receipt_sum = sum(item['price'] for item in selected_data)
            
            button_label = f"🧾 Выбрано: {len(selected_data)} поз. на сумму {receipt_sum:,.2f} сом"
            if st.button(button_label, key="toggle_selected"):
                st.session_state.show_selected = not st.session_state.show_selected

            if st.session_state.show_selected:
                for item in selected_data:
                    cols = st.columns([5, 1.5, 1.5, 2])
                    cols[0].write(item['title'])
                    cols[1].markdown(get_color_display_html(item, 'color_0'), unsafe_allow_html=True)
                    cols[2].markdown(get_color_display_html(item, 'color_1'), unsafe_allow_html=True)
                    cols[3].markdown(f"<p class='price-text'>{item['price']:,.2f} сом</p>", unsafe_allow_html=True)
            
            bottom_cols = st.columns([1, 1])
            pdf_bytes = generate_pdf_receipt(selected_data)
            if pdf_bytes:
                bottom_cols[0].download_button("Скачать чек (PDF)", data=pdf_bytes, file_name="check.pdf", mime="application/pdf")
            
            if bottom_cols[1].button("🗑️ Очистить все"):
                st.session_state.selected_analyses.clear()
                st.rerun()

    total_sum_placeholder = st.empty()
    total_sum_placeholder.markdown(f"""
    <div style="position: fixed; bottom: 10px; right: 100px; background-color: #3f51b5; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);">
        <h3 style="margin: 0; color: #ffffff;">Итого: {total_sum:,.2f} сом</h3>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# --- Main Application Logic ---
# This checks if the user is logged in. If not, it shows the login form.
# Otherwise, it runs the main application.
if not st.session_state.logged_in:
    login_form()
else:
    main_app()