import sys
import os
import pkgutil
import imp
import traceback
import i18n
from dragonfly import *
from json_parser import parse_file

# Load config.json
root_path = os.path.dirname(os.path.abspath(__file__))
config = parse_file(os.path.join(root_path, "config.json"))

absolute_modules_directory = config["modules_dir"]
if not os.path.isabs(config["modules_dir"]):
    absolute_modules_directory = os.path.join(root_path, config["modules_dir"])
absolute_config_dir = config["config_dir"]
if not os.path.isabs(config["config_dir"]):
    absolute_config_dir = os.path.join(root_path, config["config_dir"])

absolute_excluded_files = [os.path.join(absolute_modules_directory, e) for e in config["excluded"]]

i18n.load_path.append(os.path.join(root_path, "translations"))
i18n.load_path.append(os.path.join(absolute_modules_directory, "translations"))
i18n.set('locale', config["locale"])
i18n.set('fallback', 'en')

__loaded_modules = {}
__grammars = []

NATLINK = 0
WSR = 1
__engine_type = None

sys.argv = ["name"]


def __get_units():
    return [u for u in __loaded_modules.values() if u is not None]


def __call_function(unit, name, **kwargs):
    try:
        function = getattr(unit, name)
        returned = function(**kwargs)
        return returned
    except:
        print("Could not call function %s of %s:" % (name, unit))
        print(traceback.format_exc())


def __add_module(m):
    unit = None
    if "create_unit" in m.__dict__:
        u = __call_function(m, "create_unit")
        if __engine_type in u.engine_types:
            unit = u
    __loaded_modules[m] = unit


def __load_package(path, package_name):
    if path in absolute_excluded_files:
        return

    package_tuple = imp.find_module(os.path.basename(path), [os.path.dirname(path)])
    package = imp.load_module(package_name, *package_tuple)
    __loaded_modules[package] = None
    print(" - pkg %s" % package_name)
    prefix = package_name + "."
    for importer, module_name, ispkg in pkgutil.iter_modules([package_tuple[1]], prefix):
        module_path = os.path.join(path, module_name)
        if module_path in absolute_excluded_files:
            continue
        elif ispkg:
            __load_package(os.path.join(path, module_name), module_name)
        elif module_name in sys.modules:
            module = sys.modules[module_name]
            __add_module(module)
            print(" - (%s)" % module_name)
        else:
            try:
                module = importer.find_module(module_name).load_module(module_name)
                __add_module(module)
            except:
                print("Could not load %s:" % module_name)
                print(traceback.format_exc())
                continue
            else:
                print(" - %s" % module_name)


def __load_modules():
    print("\nLoading modules:")
    __load_package(os.path.join(root_path, "core"), "core")
    __load_package(absolute_modules_directory, os.path.basename(absolute_modules_directory))

    print("\nInitializing units:")
    for unit in __get_units():
        __call_function(unit, "init")


def __unload_modules():
    print("\nDestroying units:")
    for unit in __get_units():
        __call_function(unit, "destroy")

    print("\nDeleting modules:")
    for module in __loaded_modules.keys():
        del __loaded_modules[module]
        del sys.modules[module.__name__]
        print(" - %s" % module.__name__)
        del module


def __load_grammars():
    print("\nLoading grammars:")
    for unit in [u for u in __get_units() if u.grammar_name is not None]:

        def translate(key):
            return i18n.t(unit.grammar_name + "." + key)

        grammar = Grammar(unit.grammar_name)
        enabled = __call_function(unit, "create_grammar", g=grammar, t=translate)
        grammar.load()
        if not enabled:
            grammar.disable()
        print(" - %s" % grammar.name)


def __unload_grammars():
    print("\nUnloading grammars:")
    for g in __grammars:
        print(" - %s" % g.name)
        g.unload()
        __grammars.clear()


def __load_configurations():
    print("\nLoading configurations:")
    for unit in __get_units():
        __call_function(unit, "load_config", config_path=absolute_config_dir)


def get_grammars():
    return __grammars


def get_engine_type():
    return __engine_type


def save_module_data():
    data = {}
    print("\nSaving unit data:")
    for unit in __get_units():
        to_save = __call_function(unit, "save_data")
        if to_save is not None:
            data[unit.__name__] = to_save
    return data


def load_module_data(data):
    print("\nLoading unit data:")
    for unit in __get_units():
        __call_function(unit, "load_data", data=data[module.__name__])


def start(engine_type):
    global __engine_type
    __engine_type = engine_type
    __load_modules()
    __load_configurations()
    __load_grammars()


def shutdown():
    __unload_grammars()
    __unload_modules()
