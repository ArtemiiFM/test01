import streamlit as st
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Функция для проверки наличия изображения по URL
def check_image(url):
    try:
        response = requests.head(url, timeout=2)
        if response.status_code == 200:
            return True
    except:
        pass
    return False

# Функция для обработки одного ID
def process_id(id_, url_template):
    url = url_template.replace('???', str(id_))
    if check_image(url):
        return id_
    return None

def main():
    st.title("Проверка наличия изображений игроков FIFA")
    
    st.sidebar.header("Настройки")
    
    # Поле для ввода URL-шаблона
    default_url = "https://eaassets-a.akamaihd.net/fifa/u/f/fcm23/prod/s/static/players/players_24/p???_RS24_ICON_ETC2.eaz"
    url_template = st.sidebar.text_input("URL-шаблон", value=default_url)
    
    # Загрузка файла с ID (txt)
    uploaded_ids = st.sidebar.file_uploader("Загрузите файл с ID игроков (txt)", type=["txt"])
    
    # Загрузка файла с соответствием ID и фамилий (csv/xls)
    uploaded_mapping = st.sidebar.file_uploader("Загрузите файл с соответствием ID и фамилий (csv/xls)", type=["csv", "xls", "xlsx"])
    
    if uploaded_ids is not None and uploaded_mapping is not None:
        # Чтение ID игроков
        ids = []
        for line in uploaded_ids.getvalue().decode("utf-8").splitlines():
            line = line.strip()
            if line.isdigit():
                ids.append(int(line))
        
        st.write(f"Количество ID для проверки: {len(ids)}")
        
        # Чтение соответствий ID и фамилий
        try:
            if uploaded_mapping.name.endswith(('.xls', '.xlsx')):
                df_mapping = pd.read_excel(uploaded_mapping)
            else:
                df_mapping = pd.read_csv(uploaded_mapping)
            
            if df_mapping.shape[1] < 2:
                st.error("Файл соответствий должен содержать как минимум два столбца: ID и Фамилия.")
                return
            
            # Предполагается, что первый столбец - ID, второй - фамилия
            df_mapping.iloc[:,0] = df_mapping.iloc[:,0].astype(str).str.strip()
            df_mapping.iloc[:,1] = df_mapping.iloc[:,1].astype(str).str.strip()
            mapping_dict = pd.Series(df_mapping.iloc[:,1].values, index=df_mapping.iloc[:,0]).to_dict()
            
            # Для отладки: показать первые 5 элементов словаря
            st.write("Пример соответствий ID и Фамилий:")
            st.write(pd.DataFrame({
                "ID (строка)": list(mapping_dict.keys())[:5],
                "Фамилия": list(mapping_dict.values())[:5]
            }))
        except Exception as e:
            st.error(f"Ошибка при чтении файла соответствий: {e}")
            return
        
        # Кнопка для начала проверки
        if st.button("Начать проверку"):
            matched_ids = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(ids)
            processed = 0

            # Используем ThreadPoolExecutor для многопоточности
            with ThreadPoolExecutor(max_workers=700) as executor:
                future_to_id = {executor.submit(process_id, id_, url_template): id_ for id_ in ids}
                for future in as_completed(future_to_id):
                    result = future.result()
                    if result is not None:
                        matched_ids.append(result)
                    processed += 1
                    if processed % 1000 == 0 or processed == total:
                        progress = processed / total
                        progress_bar.progress(progress)
                        status_text.text(f"Обработано {processed} из {total} ID")
            
            # Формирование результата
            if matched_ids:
                df_result = pd.DataFrame(matched_ids, columns=["ID"])
                df_result["ID"] = df_result["ID"].astype(str)  # Преобразуем ID в строку для сопоставления
                df_result["Фамилия"] = df_result["ID"].map(mapping_dict)
                
                # Проверка, почему фамилия None
                missing_surnames = df_result[df_result["Фамилия"].isnull()]
                if not missing_surnames.empty:
                    st.warning(f"Не найдены фамилии для {len(missing_surnames)} ID. Проверьте формат ID в файле соответствий.")
                
                st.success("Проверка завершена!")
                st.write("Найденные совпадения:")
                st.dataframe(df_result)
                
                # Возможность скачать результат как TXT
                txt = df_result.to_csv(sep='\t', index=False).encode('utf-8')  # Используем табуляцию как разделитель
                st.download_button(
                    label="Скачать результат как TXT",
                    data=txt,
                    file_name='matched_ids.txt',
                    mime='text/plain',
                )
            else:
                st.warning("Совпадений не найдено.")

if __name__ == "__main__":
    main()