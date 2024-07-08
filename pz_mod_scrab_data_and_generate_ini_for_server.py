import requests
from bs4 import BeautifulSoup
import re
import csv
import os
import sys
import json
import pprint
import time
import random

# ------------------------------------------------------------------
# Обработка конфиг файла и объявление переменных 
# ------------------------------------------------------------------

# Чтение настроек из settings.json
with open('settings.json', 'r') as f:
    settings = json.load(f)

# Misc параметры из settings.json
base_url_collection = settings['BASE_WORKSHOP_URL_COLLECTION']  # url для сылки на Workshop для получения списка модов по его id
base_url_mod = settings['BASE_WORKSHOP_URL_MOD']  # url для сылки на Workshop для получения данных о моде по его id
delim = settings['delim']  # разделитель для CSV внутри ячейки
count_limit = settings['count_limit']  # вряд ли возможно что вложенных зависимостей может быть больше 3-5 штук, а 10 кажется не возможным событием

# Параметры путей и имен файлов
output_folder = settings['output_folder']
output_csv = settings['output_csv']
output_ini = settings['output_ini']

# Переменные для списков ID из файлов и конфига и коллекции (всё это используется для получения итогового ids)
ids_get = settings['list_ids_get']
file_ids_get = settings['file_ids_get']
file_ids_to_config = settings['file_ids_to_config']
file_ids_collection_to_config = settings['file_ids_collection_to_config']
collection_id_to_config = settings['collection_id_to_config']

# Производные перменные полных путей файлов
csv_file = os.path.join(output_folder, output_csv)  # Путь к CSV файлу для записи данных
ini_file = os.path.join(output_folder, output_ini)  # Путь для ini-файла
ids_file = os.path.join(output_folder, file_ids_collection_to_config)

# Исключения и включения для генерации ini
include_workshop_items = set(settings['include']['WorkshopItems'])
include_mods = set(settings['include']['Mods'])
include_map = set(settings['include']['Map'])

exclude_workshop_items = set(settings['exclude']['WorkshopItems'])
exclude_mods = set(settings['exclude']['Mods'])
exclude_map = set(settings['exclude']['Map'])

multi_items = settings['multi_items']
pprint.pprint(multi_items)

# названия атрибутов в ini конфиге
name_ini_section = ['WorkshopItems', 'Mods', 'Map']

# Задаём имена столбцов для CSV
# первый id который проверям, второй id который получаем (в идеали должны совпадать :)
# 'Workshop ID', 'Mod ID', 'Map Folder' стадартные имена употребляемые в workshop 
# Dependencies это те что из "Required items"
# URL для удобства открытия страницы в браузере из консоли
# TODO: ищется способ автоматически подписаться на мод по url (но не факт что это нужно :)
rows = ['ID', 'Workshop ID', 'Mod ID', 'Map Folder', 'Dependencies IDs', 'Workshop URL']

# Define regular expressions for extracting Workshop ID, Mod ID, and Map Folder
workshop_id_regex = rf'{rows[1]}:\s*(\d+)'
mod_id_regex = rf'{rows[2]}:\s*([^\n\r<]+)'
map_folder_regex = rf'{rows[3]}:\s*([^\n\r<]+)'


def scrab_collection_ids(id):
    """
    Скрабинг списка ids из коллекции по её id
    Возращает множество ids
    A так же записывает данные в файл
    """

    workshop_url = base_url_collection + str(id)
    ids = set()


    # Запрос HTML-контента страницы
    response = requests.get(workshop_url)
    if response.status_code != 200:
        sys.stderr.write(f"!! Failed to retrieve content from {workshop_url}. Status code: {response.status_code}")
        return
    
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    collectionChildren_div = soup.find('div', class_='collectionChildren')

    # Если не найден элемент с классом 'collectionChildren', возвращаем пустой список
    if not collectionChildren_div:
        sys.stderr.write(f"!! not found div {workshop_url}")
        return ids

    # Находим все элементы <div class="workshopItem"> внутри collectionChildren_div
    workshop_items = collectionChildren_div.find_all('div', class_='workshopItem')

    # Проходимся по каждому элементу и извлекаем id из ссылки
    for item in workshop_items:
        link = item.find('a')  # Находим первую ссылку внутри элемента <div class="workshopItem">
        if link:
            href = link.get('href')  # Получаем значение атрибута href
            # Ищем числовой id в конце URL
            id_index = href.rfind('=')  # Находим позицию последнего знака "=" в строке
            if id_index != -1:
                numeric_id = href[id_index + 1:]  # Получаем числовой id, который идет после "="
                ids.add(numeric_id)
    
    write_set_to_file(ids, ids_file)

    return ids

def scrab_metadata(id):
    """
    Скрабинг данных мода для PZ из Steam Workshop по ID
    на данный момент возвращает пять порядковых значений
    workshop_id, mod_ids, map_folders, dependencies, workshop_url
    """
    
    # Формирование полной ссылки
    workshop_url = base_url_mod + str(id)
    workshop_id = None
    mod_ids, map_folders = set(), set()
    dependencies = []

    mod_folder  = os.path.join(output_folder,  f"{id}")
    if not os.path.exists(mod_folder):
        os.makedirs(mod_folder)

    # Запрос HTML-контента страницы
    response = requests.get(workshop_url)
    if response.status_code != 200:
        sys.stderr.write(f"!! Failed to retrieve content from {workshop_url}. Status code: {response.status_code}")
        return
    
    html_content = response.text

    # записываем html-контент страницы
    html_filename = os.path.join(mod_folder,  f"{id}_FullPage.html")
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)


    # Парсинг HTML с помощью BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')


    # ------------------------------------------------------------------------  
    # Собираем данные о моде из блока с описанием
    # ------------------------------------------------------------------------  

    # Находим блок div с классом 'workshopItemDescription'
    description_div = soup.find('div', class_='workshopItemDescription')

    # записываем обрабатываемый div в отдельный файл
    if description_div:
        div_filename = os.path.join(mod_folder,  f"{id}_workshopItemDescription.html")
        with open(div_filename, 'w', encoding='utf-8') as f:
            f.write(description_div.prettify())

        # Извлекаем все текстовые строки внутри div с учетом тегов <br>
        lines = []
        for elem in description_div.descendants:
            if isinstance(elem, str):  # Если элемент строка
                lines.extend(elem.splitlines())  # Добавляем строки, разделяя по символам новой строки
            # elif elem.name == 'br':  # Если элемент тег <br>
            #     lines.append('')  # Добавляем пустую строку на место тега <br>

        # Объединяем строки в один текст
        text = '\n'.join(lines)


        # Find all uniq of Mod ID and Map Folder
        mod_ids.update(re.findall(mod_id_regex, text))
        map_folders.update(re.findall(map_folder_regex, text))

        # Extract Workshop ID
        workshop_id_matches = re.findall(workshop_id_regex, text)

        # Remove whitespace from extracted values
        mod_ids = {s.strip() for s in mod_ids if s.strip()}
        map_folders = {s.strip() for s in map_folders if s.strip()}
        workshop_id_matches[:] = [s.strip() for s in workshop_id_matches if s.strip()]

        if str(id) in workshop_id_matches:
            workshop_id = id
        else:
            sys.stderr.write(f"!! Failed to find 'Workshop ID:' in the HTML content for id={id}, check this manualy")

    else:
        print(f"Failed to find workshopItemDescription div in the HTML content for {id}")
        return

    # ------------------------------------------------------------------------  
    # Находим зависимости от других модов
    # ------------------------------------------------------------------------  

    # Находим блок div с классом 'requiredItemsContainer'
    required_items_div = soup.find('div', class_='requiredItemsContainer')

    # записываем обрабатываемый div в отдельный файл
    if required_items_div:
        div_filename = os.path.join(mod_folder,  f"{id}_requiredItemsContainer.html")
        with open(div_filename, 'w', encoding='utf-8') as f:
            f.write(required_items_div.prettify())

    if required_items_div:
        # Находим все ссылки в блоке requiredItemsContainer
        links = required_items_div.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Извлекаем Workshop ID из ссылки
            match = re.search(r'id=(\d+)', href)
            if match:
                dependency_id = match.group(1)
                dependencies.append(dependency_id)



    # Запсивыем представление данных мода в отдельный файл
    repr_filename = os.path.join(mod_folder,  f"{id}_repr.txt")
    with open(repr_filename, 'w', encoding='utf-8') as f:
        data = f"{rows[1]}: {workshop_id}\n{rows[2]}: {delim.join(mod_ids)}\n{rows[3]}: {delim.join(map_folders)}\n{rows[4]}: {delim.join(dependencies)}\n{rows[5]}:{workshop_url}"
        f.write(data)

    return workshop_id, mod_ids, map_folders, dependencies, workshop_url


def write_row_to_csv(id, workshop_id, mod_ids, map_folders, dependencies, workshop_url):
    """
    Построчная запсь переданных данных в файл CSV
    """
    # Определяем режим открытия файла в зависимости от его существования
    mode = 'a' if os.path.exists(csv_file) else 'w'

    with open(csv_file, mode, newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        # Если файл только что создан, записываем заголовки
        if mode == 'w':
            writer.writerow(rows)

        writer.writerow([id, workshop_id, delim.join(mod_ids), delim.join(map_folders), delim.join(dependencies), workshop_url])


def processed_ids(ids):
    """
    Запуск обработки списка ID
    """
    print(f"Processed for {ids}")
    F = False
    i=0
    for id in ids:
        i += 1
        print(f"==> {i}/{len(ids)}", end=': ')
        if is_id_in_csv(id):
            print(f"skip id={id} because is exist")
            continue

        # получаем данные из HTML страницы и записываем в CSV файл-данных
        workshop_id, mod_ids, map_folders, dependencies, workshop_url = scrab_metadata(id)
        write_row_to_csv(id, workshop_id, mod_ids, map_folders, dependencies, workshop_url)
        print(f"add id={id}")
        F = True

    if F:
        print(f'\nData has been written to {csv_file}')


def find_missing_dependencies():
    """
    Формирование уникальных отсутсвующих ID модов из списка зависимостей существующего CSV файла данных
    """
    # Список для хранения всех зависимостей из файла
    all_dependencies = set()

    # Чтение данных из CSV файла
    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            # Получаем строку с зависимостями, разбиваем по запятым и добавляем в множество
            dependencies_str = row[rows[4]]
            dependencies = dependencies_str.split(delim) if dependencies_str else []
            all_dependencies.update(dependencies)

    # Список всех Workshop IDs из файла
    all_workshop_ids = set()
    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            workshop_id = row[rows[1]]
            all_workshop_ids.add(workshop_id)

    # Находим уникальные зависимости, которые отсутствуют в Workshop IDs
    missing_dependencies = all_dependencies - all_workshop_ids

    return list(missing_dependencies)


def is_id_in_csv(id_to_check):
    """
    Функция для проверки наличия ID в файле CSV.
    """
    id_column=rows[0] # проверяем по ID колонки, так как id пишем сами не зависимо от того соскрабили его или нет
    try:
        # Читаем данные из CSV файла
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                if row[id_column] == str(id_to_check):
                    return True
        return False
    except Exception as e:
        return False


def generate_ini_section(ids):
    """
    Функция для генерации секции ini из метаданных модов.
    ids: множество id, метаданные которых должны быть включене в атрибиты ini конфига, 
        в соответсвии с включениями и исключениями из settings.json
    """
    ini1 = name_ini_section[0]
    ini2 = name_ini_section[1]
    ini3 = name_ini_section[2]
    data = {
        ini1: set(),
        ini2: set(),
        ini3: set()
    }

    # Сея реализация проста от слова simple, которая перебирает строки в CSV и если id совпадает, то помещает данные этого мода в множество для соответствующего аттрибута,
    # при этом базируется на том что ids передается вместе с зависимостями, т.е. зависимости должны быть уже включены в передаваемом списке ids
    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                if row[rows[0]] in ids:
                    # Добавляем Workshop ID, Mod IDs и Maps в множество, чтобы сохранить уникальность
                    if row[rows[1]]:
                        data[ini1].add(row[rows[1]])
                    if row[rows[2]]:
                        # Разделяем значение по разделителю и добавляем в множество ключа mods
                        data[ini2].update(row[rows[2]].split(delim))
                    if row[rows[3]]:
                        # Разделяем значение по разделителю и добавляем в множество ключа maps
                        data[ini3].update(row[rows[3]].split(delim))
        

        # Эта простая реализация включения и исключения по полному соответсвию указаной строки в файле-сеттингс используя множества
        if include_workshop_items:
            data[ini1] = data[ini1].union(include_workshop_items)
        if include_mods:
            data[ini2] = data[ini2].union(include_mods)
        if include_map:
            data[ini3] = data[ini3].union(include_map)

        if exclude_workshop_items:
            data[ini1] = data[ini1].difference(exclude_workshop_items)
        if exclude_mods:
            data[ini2] = data[ini2].difference(exclude_mods)
        if exclude_map:
            data[ini3] = data[ini3].difference(exclude_map)

        # TODO: тут реализация для multi_items

        # Обработка multi_items
        for item in multi_items:
            workshop_item_id = item.get("WorkshopItems")
            if not workshop_item_id:
                continue

            # Если указанный WorkshopItemID присутствует, применяем указанные включения и исключения
            if workshop_item_id in data[ini1]:
                # Применение включений
                if "include" in item:
                    if "Mods" in item["include"]:
                        data[ini2].update(item["include"]["Mods"])
                    if "Map" in item["include"]:
                        data[ini3].update(item["include"]["Map"])

                # Применение исключений
                if "exclude" in item:
                    if "Mods" in item["exclude"]:
                        data[ini2].difference_update(item["exclude"]["Mods"])
                    if "Map" in item["exclude"]:
                        data[ini3].difference_update(item["exclude"]["Map"])


        # Создаем строки для INI файла
        workshop_ids_str = ';'.join(data[ini1])
        mods_str = ';'.join(data[ini2])
        maps_str = ';'.join(data[ini3])

        # в 42 неожиданное требование что бы был вначале слеш у каждого каждого Mod_ID типа '\tsarslib'
        mods_str = ';'.join('\\' + item for item in data[ini2])

        # Всегда добавляем "Muldraugh, KY" в maps_str и строго последним :-),
        # и поэтому хардкодим ;-)
        if maps_str:
            maps_str += ";Muldraugh, KY"
        else:
            maps_str += "Muldraugh, KY"


        # Формируем ini секцию
        ini_section = f"WorkshopItems={workshop_ids_str}\n"
        ini_section += f"Mods={mods_str}\n"
        ini_section += f"Map={maps_str}\n"

        return ini_section

    except FileNotFoundError:
        sys.stderr.write(f"!! CSV file '{csv_file}' not found.")
        return ""
    except Exception as e:
        sys.stderr.write(f"!! Error occurred while generating ini section: {e}")
        return ""


def write_ini_file(ini_section):
    """
    Функция для записи секции ini в файл.
    """
    try:
        with open(ini_file, 'w', encoding='utf-8') as file:
            file.write(ini_section)
        print(f"\nSuccessfully wrote ini section to '{ini_file}'.")
    except Exception as e:
        sys.stderr.write(f"!! Error occurred while writing ini file: {e}")


def read_ids_file(ids_file):
    """
    Функция для чтения идентификаторов из файла.
    Один id на строку.
    Возвращает множество ids.
    Если файла нет, возвращает пустое множество.
    """
    ids = set()
    try:
        with open(ids_file, 'r') as f:
            ids = [line.strip() for line in f if line.strip().isdigit()]
    except FileNotFoundError:
        pass

    return ids

def get_all_dependencies(target_id):
    """
    Рекурсивно собирает все зависимости для заданного id из CSV файла
    target_id: идентификатор, для которого необходимо собрать зависимости

    Возвращает множество из id для всех зависимостей наличиствующие у переданного id.
    """
    dependencies = set()

    def recursive_dependency_search(id_to_search):
        nonlocal dependencies
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                current_id = row[rows[0]]
                dependency_ids = row[rows[4]].split(delim) if row[rows[4]] else []

                # выбираем только тот mod_id, который нас интересует
                if current_id == id_to_search:
                    # и в тоже время не находится в исключении для конфига он либо его зависимость
                    if current_id not in exclude_workshop_items:
                        for dep_id in dependency_ids:
                            if dep_id not in exclude_workshop_items:
                                dependencies.add(dep_id)
                                # TODO: тута видимо добавить проверку на существование данных этого id в имеющихся данных CSV файла
                                # и если вдруг их нема, то сделать колбэк, сходить рпц вызовом или вызвать вызвать функцию что бы их получить

                                # проверяем что его ещё нету в возвращаемом множестве, иначе получается циклическая рукурсия
                                if not dep_id in dependencies:
                                    # и ищём зависимости у зависимости :)
                                    recursive_dependency_search(dep_id)
                        # ? после найденного наверное очевидно можно завершить сравнение в переборе
                    break
            else:
                # а если нету в CSV кэш-файле то запрашиваем
                processed_ids([current_id])
                random_delay = random.uniform(1, 5) 
                time.sleep(random_delay) # что бы избежать 429, ну или делать ещё дополнительно проверку статуса
                # и вызываем повторно
                recursive_dependency_search(current_id)

    recursive_dependency_search(target_id)
    return dependencies


def write_set_to_file(data_set, output_file):
    """
    Функция для записи элементов множества в файл построчно.
    """
    with open(output_file, 'w') as f:
        for item in data_set:
            f.write(str(item) + '\n')


# ------------------------------------------------------------------
# Подготовка окружения
# ------------------------------------------------------------------

# Создаем папку output, если она не существует
if not os.path.exists(output_folder):
    os.makedirs(output_folder)


# ------------------------------------------------------------------
# Первоначальная обработка списков ID
# для получение множества ids, которое для скрибинга метаданных каждого id мода
# ------------------------------------------------------------------
ids_get_file = read_ids_file(file_ids_get)
ids_config_file = read_ids_file(file_ids_to_config)
ids_collection_file = read_ids_file(ids_file)
ids_collection = set()

# Если есть коллекция в конфиге и нету кэш-файла, то скрабим множестов ids по этой колеекции 
if collection_id_to_config and not os.path.exists(ids_file):
    ids_collection = scrab_collection_ids(collection_id_to_config)

# Объединение множеств ID для скрабинга по нему (множеству) всех итоговых их (модов) метаданных (ака кэш)
ids = set(ids_get) | set(ids_get_file) | set(ids_config_file) | set(ids_collection_file) | set(ids_collection) 

processed_ids(ids)


# ------------------------------------------------------------------
# Последующая циклическая обработка зависимостей из CSV файла
# ------------------------------------------------------------------
while True:
    # Находим отсутствующие зависимости
    ids_missing_dependencies = find_missing_dependencies()
    # уменьшаем счетчик
    count_limit -= 1

    # Если нету отсутствующих зависимостей в наших данных или зацикленность, то завершаем цикл
    if not ids_missing_dependencies or not count_limit:
        break

    # Обрабатываем найденные зависимости
    processed_ids(ids_missing_dependencies)


# ------------------------------------------------------------------
# Формирование секций для ini файла по CSV файлу с данными
# ------------------------------------------------------------------
# TODO: приоретеное формирование множества id из файла указанного в file_ids_to_config или что-то из ids_collection ids_collection_file
# или всего CSV (что вероятно бессмысленно :)

ids_to_gen_config_with_depend = set()
ids_to_gen_config = set()
if ids_config_file:
    ids_to_gen_config = set(ids_config_file)
    ids_to_gen_config_with_depend = set(ids_config_file)
elif ids_collection_file:
    ids_to_gen_config = set(ids_collection_file)
    ids_to_gen_config_with_depend = set(ids_collection_file)
elif ids_collection:
    ids_to_gen_config = set(ids_collection)
    ids_to_gen_config_with_depend = set(ids_collection)

# и обогащаем включениями из сеттингс
ids_to_gen_config = ids_to_gen_config.union(include_workshop_items)
# по этому множеству id создаем список всех id c учётом зависимостей модов друг от друга
for id in ids_to_gen_config:
    ids_to_gen_config_with_depend.update(get_all_dependencies(id))
# и отшлаковываем исключениями из сеттингс
ids_to_gen_config_with_depend = ids_to_gen_config_with_depend.difference(exclude_workshop_items)

# Генерируем ini секцию
ini_section = generate_ini_section(ids_to_gen_config_with_depend)

# Если удалось сгенерировать ini секцию, записываем ее в файл и печатаем
if ini_section:
    write_ini_file(ini_section)
    print("\nПараметры для конфигурации сервера:")
    print(ini_section)
else:
    sys.stderr.write(f"!! Failed to generate ini section.")


# ------------------------------------------------------------------
# Сравнение конфига сервера если он есть с генирируемыми параметрами
# ------------------------------------------------------------------
# TODO: сравнение конфига сервера если он есть с генирируемыми параметрами
