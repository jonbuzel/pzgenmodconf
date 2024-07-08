def load_simple_ini_file(filename):
    with open(filename, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    config = {}
    for line in lines:
        line = line.strip()
        if line.startswith('Mods='):
            config['Mods'] = line.split('=')[1].split(';')
        elif line.startswith('Map='):
            config['Map'] = line.split('=')[1].split(';')
        elif line.startswith('WorkshopItems='):
            config['WorkshopItems'] = line.split('=')[1].split(';')
    return config

def compare_attributes(attr_name, config_a, config_b):
    if attr_name not in config_a or attr_name not in config_b:
        return None

    set_a = set(config_a[attr_name])
    set_b = set(config_b[attr_name])

    in_a_not_in_b = set_a - set_b
    in_b_not_in_a = set_b - set_a

    return {
        'in_a_not_in_b': list(in_a_not_in_b),
        'in_b_not_in_a': list(in_b_not_in_a)
    }

def main():
    file_a = 'pz_server.ini'
    file_b = 'output/pz_config_for_server.ini'

    config_a = load_simple_ini_file(file_a)
    config_b = load_simple_ini_file(file_b)

    # Сравниваем атрибуты WorkshopItems
    workshop_items_comparison = compare_attributes('WorkshopItems', config_a, config_b)
    if workshop_items_comparison:
        print(f"\n\nРазличия в атрибуте WorkshopItems:")
        print(f"Элементы в {file_a}, отсутствующие в {file_b}: {workshop_items_comparison['in_a_not_in_b']}")
        print(f"Элементы в {file_b}, отсутствующие в {file_a}: {workshop_items_comparison['in_b_not_in_a']}")
    else:
        print("Атрибут WorkshopItems отсутствует в одном из файлов.")

    # Сравниваем атрибуты Mods
    mods_comparison = compare_attributes('Mods', config_a, config_b)
    if mods_comparison:
        print(f"\n\nРазличия в атрибуте Mods:")
        print(f"Элементы в {file_a}, отсутствующие в {file_b}: {mods_comparison['in_a_not_in_b']}")
        print(f"Элементы в {file_b}, отсутствующие в {file_a}: {mods_comparison['in_b_not_in_a']}")
    else:
        print("Атрибут Mods отсутствует в одном из файлов.")

    # Сравниваем атрибуты Map
    map_comparison = compare_attributes('Map', config_a, config_b)
    if map_comparison:
        print(f"\n\nРазличия в атрибуте Map:")
        print(f"Элементы в {file_a}, отсутствующие в {file_b}: {map_comparison['in_a_not_in_b']}")
        print(f"Элементы в {file_b}, отсутствующие в {file_a}: {map_comparison['in_b_not_in_a']}")
    else:
        print("Атрибут Map отсутствует в одном из файлов.")

if __name__ == "__main__":
    main()
