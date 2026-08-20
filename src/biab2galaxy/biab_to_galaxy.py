import yaml
from pathlib import Path
from warnings import warn
import json
import os
import shutil
from lxml import etree as ET
from argparse import ArgumentParser
from platformdirs import user_config_dir
from importlib.resources import files
from .generate_data import generate_data, declare_tables
from types import ModuleType

biab2galaxy_config_dir = Path(user_config_dir("biab2galaxy"))
biab2galaxy_config_dir.mkdir(parents=True, exist_ok=True)
type_to_extension_path = biab2galaxy_config_dir / "type_to_extension.json"
if not type_to_extension_path.exists():
    shutil.copy(files("biab2galaxy").joinpath("type_to_extension.json"), type_to_extension_path)

# opens a dictionnary mapping MIME types to file extensions.
# Biab uses MIME types to describe files, Galaxy uses extension (format="...")
with open(type_to_extension_path, "r") as file:
    file_str = file.read()
    TYPE_TO_EXTENSION = json.loads(file_str)

PYTHON_DEFUALT_DEPENDENCIES = {
    "pystac"
    }

R_DEFAULT_DEPENDENCIES = {
    "conda-build",
    "proj",
    "libgdal",
    "r-abind",
    "r-base",
    "r-curl",
    "r-devtools",
    "r-dismo",
    "r-downloader",
    "r-dplyr",
    "r-enmeval",
    "r-essentials",
    "r-gdalcubes",
    "r-gdalutilities",
    "r-gdalutils",
    "r-geojsonsf",
    "r-ggsci",
    "r-jpeg",
    "r-landscapemetrics",
    "r-magrittr",
    "r-png",
    "r-proj",
    "r-purrr",
    "r-rcurl",
    "r-remotes",
    "r-rgbif",
    "r-rjava",
    "r-rjson",
    "r-rnaturalearth",
    "r-rnaturalearthdata",
    "r-rredlist",
    "r-rstac",
    "r-sf",
    "r-stars",
    "r-stringr",
    "r-stringr",
    "r-terra",
    "r-this.path",
    "r-tidyselect",
    "r-tidyverse",
    "r-stringr",
    "r-proj",
    "duckdb"
    }

JULIA_DEFAULT_DEPENDENCIES = {
    }

EXT_2_DEPENDENCIES = {
    ".jl": JULIA_DEFAULT_DEPENDENCIES,
    ".r": R_DEFAULT_DEPENDENCIES,
    ".py": PYTHON_DEFUALT_DEPENDENCIES
    }

EXT_TO_INTERPRETER = {
    ".jl": "julia",
    ".r": "Rscript",
    ".py": "python"
    }

SPECIAL_TYPES = {"country", "countryRegion", "countryRegionCRS", "CRS", "bboxCRS"}

def get_yaml_data(galaxy_wrapper_path: Path, biab_wrapper_path: Path = None) -> dict | None:
    """
    Loads a yaml file into a dict structure.
    Creates the parent directory if doesn't exist yet

    Parameters
    ----------
    galaxy_wrapper_path : Path
        path of the galaxy wrapper .xml file.
    biab_wrapper_path : Path, optional
        path of the biab wrapper .yml file. The default is None.

    Raises
    ------
    RuntimeError
        error while reading biab wrapper.

    Returns
    -------
    yaml_data : dict | None
        data of the biab wrapper or None if no biab wrapper is provided.
    """
    if biab_wrapper_path is None:
        return None
    if galaxy_wrapper_path is not None:
        os.makedirs(os.path.dirname(galaxy_wrapper_path), exist_ok=True)
    # LOADING files
    print("reading biab .yml wrapper")
    with open(biab_wrapper_path) as yaml_file:
        try:
            yaml_data = yaml.safe_load(yaml_file)
        except yaml.YAMLError:
            raise RuntimeError(f"error while reading biab wrapper {biab_wrapper_path}")
    return yaml_data


def generate_dot_shed(shed_path: Path, yaml_data: dict):
    """
    Generates a .shed.yml file based on some infos of the biab wrapper.
    This file is not required to have a functionning tool.
    Creates the parent directory if it doesn't already exist

    Parameters
    ----------
    shed_path : Path
        path of the shed file to be created.
    yaml_data : dict
        data of the biab wrapper.
    """
    os.makedirs(os.path.dirname(shed_path), exist_ok=True)
    dot_shed = {}
    
    if 'name' in yaml_data:
        dot_shed["name"] = yaml_data['name']
    
    if yaml_data.get('author') and len(yaml_data['author']) > 0:
        if 'name' in yaml_data['author'][0]:
            dot_shed["owner"] = yaml_data['author'][0]['name']
        if 'identifier' in yaml_data['author'][0]:
            dot_shed["homepage_url"] = yaml_data['author'][0]['identifier']
    
    if 'description' in yaml_data:
        dot_shed["description"] = yaml_data['description']
        dot_shed["long_description"] = yaml_data['description']
    
    if 'license' in yaml_data:
        dot_shed["type"] = yaml_data["license"]
        
    dot_shed["remote_repository_url"] = "https://github.com/GEO-BON/bon-in-a-box-pipelines/tree/main/scripts"
    dot_shed["categories"] = []
    
    if 'name' in yaml_data:
        dot_shed["auto_tool_repositories"] = [{
            "name_template": "{{ tool_id }}",
            "description_template": yaml_data['name'] + ": {{ tool_id }}"
        }]
    
    print("writing .shed.yml file")
    with open(shed_path, "w") as file:
        yaml.dump(dot_shed, file)
        
        
def generate_data_tables(galaxy_path: Path):
    """
    Generates data tables location files of countries and regions in the galaxy instance.
    This files are used by tools using biab special types.

    Parameters
    ----------
    galaxy_path : Path
        path of the galaxy instance.
    """
    tool_data_conf_path = Path(galaxy_path) / "config" / "tool_data_table_conf.xml.sample"
    regions_path = Path(galaxy_path) / "tool-data" / "regions.loc"
    countries_path = Path(galaxy_path) / "tool-data" / "countries.loc"
    if not (os.path.isfile(regions_path) and os.path.isfile(countries_path)):
        generate_data(countries_path, regions_path)
        declare_tables(tool_data_conf_path)
    else:
        print("regions and countries data tables already present")
        

def generate_script(script_processor: ModuleType, biab_script_path: Path, galaxy_script_path: Path, yaml_data: dict = None):
    """
    Generates the galaxy tool script based on the biab tool script.
        Replaces the biab_function by their definition
        Adds code to get the inputs from inputs.json
        Adds code that handles the ouputs in order to be detected properly by galaxy (if the biab wrapper is provided)
    Creates the parent directory if it doesn't already exist.

    Parameters
    ----------
    script_processor : ModuleType
        python module processing the script of that language.
    biab_script_path : Path
        path of the biab script.
    galaxy_script_path : Path
        path of the galaxy tool's script to be created.
    yaml_data : dict, optional
        data of the biab tool's wrapper. The default is None.
    """          
    os.makedirs(os.path.dirname(galaxy_script_path), exist_ok=True)
    shutil.copy(biab_script_path, galaxy_script_path)
    print(f"adapting {os.path.basename(biab_script_path)}")
    print("\treplacing biab dedicated functions")
    script_processor.replace_biab_functions(galaxy_script_path)
    print("\tadding inputs handling")
    # rewrites biab_input function, replace it by the reading of input.json
    script_processor.add_inputs_handling(galaxy_script_path)
    if yaml_data != None:
        output_replacements = {}
        for data_name, data_data in yaml_data['outputs'].items():
            file_extension = "json" if data_data['type'] in SPECIAL_TYPES else get_extension(data_data['type'])
            output_replacements[data_name] = data_name
            if not data_data['type'].endswith("[]"):
                output_replacements[data_name] += "."+file_extension
        print("\tadding outputs handling")
        # rewrites biab_output function, replace it by a rename to a predictable filename
        script_processor.add_outputs_handling(galaxy_script_path, output_replacements)
        #TODO change add_outputs_handling so that if output_replacements is None use placeholder names instead


def add_tool_to_tool_conf(galaxy_path: Path, galaxy_wrapper_path: Path, galaxy_script_path: Path):
    """
    Registers the tool to tool_conf.xml.sample in the galaxy instance, this makes the tool visible in the tools list

    Parameters
    ----------
    galaxy_path : Path
        path of the galaxy instance.
    galaxy_wrapper_path : Path
        path of the galaxy tool's wrapper.
    galaxy_script_path : Path
        path of the galaxy tool's script.
    """
    print("adding the tool to the tool_conf file")
    tool_conf_path = Path(galaxy_path) / "config" / "tool_conf.xml.sample"
    tool_conf = ET.parse(tool_conf_path)
    toolbox = tool_conf.getroot()
     
    section_attrib = {'id': 'biab', 'name': 'biab'}
    section = toolbox.findall('section')[-1]
    if section.get('id') != "biab":
        section = ET.SubElement(toolbox, 'section', section_attrib)
    
    # path of the galaxy script file including its parent directory
    path_of_galaxy_script = Path(galaxy_wrapper_path)
    file_attr = str(Path(*path_of_galaxy_script.parts[-2:]))
    
    existing_tool = None
    for tool_line in section.findall('tool'):
        if tool_line.get('file') == file_attr:
            existing_tool = tool_line
            break
    
    if existing_tool is None:
        tool_ine = ET.SubElement(section, 'tool', {"file": file_attr})
    
    tool_conf.write(tool_conf_path, encoding='utf-8', xml_declaration=True)
    
    #copy data-formater.py to to the galaxy tool directory
    shutil.copy2(Path(__file__).resolve().parent / "data-formater.py", Path(galaxy_script_path).parent / "data-formater.py")

    
def _add_options(parent: ET.Element, options_list: iter) -> list[ET.Element]:
    """
    Used by generate_wrapper to create a list of options in xml

    Parameters
    ----------
    parent : ET.Element
        Usually the 'param' xml tag in the galaxy wrapper.
    options_list : iter
        list of values of options.
    """
    for option_name in yaml_options:
        option = ET.SubElement(parent, 'option', {"value":option_name})
        option.text = option_name
        
def get_extension(yaml_type: str) -> str:
    """
    Returns the file extension associated to a biab/MIME type by searching in ~/config/biab2galaxy/type_to_extension.json
    Handles collection types

    Parameters
    ----------
    yaml_type : str
        biab data type or MIME type.

    Returns
    -------
    str
        file extension (without the ".").
    """
    base_type = yaml_type
    if yaml_type.endswith("[]"):
        base_type = yaml_type[:-2]
    if base_type in TYPE_TO_EXTENSION:
        print(f"searching extensions for {yaml_type} type")
        return TYPE_TO_EXTENSION[base_type]
    else:
        warn(f"No extension found for type {base_type}, consider adding it to ~/config/biab2galaxy/type_to_extension.json")
        return "EXTENSION"
    
def generate_wrapper(script_processor: ModuleType, yaml_data: dict, galaxy_wrapper_path: Path, biab_script_path: Path = None, galaxy_script_path: Path = None):
    """
    Generates the Galaxy tool's wrapper based on the biab tool's wrapper.
    Help section, requirements, inputs, params, ooutputs, cheetah command and the credentials sections (if the Galaxy tool's script is provided).
    Creates the parent directory if it doesn't already exist.

    Parameters
    ----------
    script_processor : ModuleType
        python module processing the script of that language.
    yaml_data : dict
        data of the biab tool's wrapper.
    galaxy_wrapper_path : Path
        path of the Galaxy tool's wrapper.
    biab_script_path : Path, optional
        path of the biab tool's script. The default is None.
    galaxy_script_path : Path, optional
        path of the Galaxy script path. The default is None.
    """
    os.makedirs(os.path.dirname(galaxy_wrapper_path), exist_ok=True)
    script_ext = Path(biab_script_path).suffix.lower()          
    
    #saving descriptions for the help section
    help_text = ""
    
    #TOOL
    script_filename = yaml_data['script']
    tool_attrib = {"id": Path(script_filename).stem,
                   "name": yaml_data['name'],
                   "version":"1.0"
        }
    
    tool = ET.Element('tool', tool_attrib)
    
    #DESCRIPTION
    short_description = yaml_data['description'].split(".")[0]+"."
    description = ET.SubElement(tool, 'description')
    description.text = short_description
    
    #REQUIREMENTS
    requirements = ET.SubElement(tool, 'requirements')
    
    #REQUIREMENT
    yaml_requirements = yaml_data['conda']['dependencies'] if "conda" in yaml_data else EXT_2_DEPENDENCIES[script_ext]
    
    print("listing conda requirements")
    for yaml_requirement in yaml_requirements:
        package = yaml_requirement
        requirement_attrib = {"type": "package"}
        if "=" in yaml_requirement:
            package, version = yaml_requirement.split("=")
            requirement_attrib['version'] = version
        
        requirement = ET.SubElement(requirements, 'requirement', requirement_attrib)
        requirement.text = package
    
    #COMMAND
    command = ET.SubElement(tool, 'command', {"detect_errors": "exit_code"})
    # The inputs are not passed as arguments to the tool scrit, instead it's passed to data-formater.py that creates an input.json file containing inputs data converted to the intended format.
    # input.json file is a dictionnary where keys are the params name and the values are either boolean, integer, float, text or a file path (can be inside a list).
    command.text = "\n\npython '$__tool_directory__/data-formater.py'\n"
    
    #INPUTS
    help_text+= "## INPUTS ##\n"
    inputs = ET.SubElement(tool, 'inputs')
    
    #PARAMS
    primitive_types = {
        "boolean": "boolean",
        "int": "integer",
        "float": "float",
        "options": "select",
        "text": "text",
        "text[]": "text" # a collection of texts appear as a text in the interface but processed differntely by data-formater
        }
            
    inputs_args_cmd = []
    rename_inputs_code = ""
    
    for param_name, param_data in yaml_data['inputs'].items():
        
        example = "" if param_data['example'] == None else f"example: {param_data['example']}"
        help_text += param_data['label']+":\n\t"+param_data['description']+"\n\t"+example+"\n"
    
        param_attrib = {"name": param_name,
                        "label": param_data['label'],
                        "help": example+" description: "+param_data['description'],
                        "optional": "true" #all parameters should be optional because there is no keyword for optional biab parameter
            }    
        
        yaml_type = param_data['type']
            
        inputs_args_cmd.append(param_name)
        param = ET.SubElement(inputs, 'param', param_attrib)
        if yaml_type in SPECIAL_TYPES:
            param.attrib['type'] = "data"
            param.attrib['format'] = "json"
            param.attrib['help'] += "\nthis file can be generated by Biab special type input generator"
        elif "options" in yaml_type:            
            yaml_options = param_data['options']
            _add_options(param, yaml_options)
            param.attrib['type'] = "select"
            
            if yaml_type.endswith("[]"):
                param.attrib['multiple'] = "true"
                
        elif yaml_type in primitive_types:
            param.attrib['type'] = primitive_types[yaml_type]
        
        elif yaml_type.endswith("[]"):
            param.attrib['type'] = "data_collection"
            ext = get_extension(yaml_type)
            if ext != "":
                param.attrib["format"] = ext
            param.attrib['help'] += f" format: list of comma separated values of {yaml_type[:-2]} types"
            # this command creates for each data_collection in input a folder containing each element (file) of the collection
            # and links the files to their original names
            rename_inputs_code += \
    f"""
    mkdir {param_name} &&
    #set ${param_name}_names = ''
    #for ${param_name}_elm in ${param_name}:
    ln -s '${param_name}' '{param_name}/${{{param_name}_elm.element_identifier}}' &&
    #set ${param_name}_names += ${{{param_name}_elm.element_identifier}} + ","
    #end for
    """
        
        else:
            ext = get_extension(yaml_type)
            param.attrib['type'] = "data"
            if ext != "":
                param.attrib["format"] = ext
            # some biab script need to know the names of input files but Galaxy renames them
            # this command creates a symbolic link from the element indentifier (displayed name) of the Galaxy item to the actual file
            rename_inputs_code += f"\nln -s '${param_name}' '${{{param_name}_elm.element_identifier}}';"       
        
        collection_suffix = "_name" if yaml_type.endswith("[]") else ""
        command.text += f"\t'{param_name}' '{yaml_type}' '${param_name+collection_suffix}'\n"
    
    
    #OUTPUTS
    output_replacements = {} #The following task is partly repeated in generate_script but I keep it here because it's easier to understand in this context
    help_text += "## OUTPUTS ##\n"
    outputs = ET.SubElement(tool, 'outputs')
    
    #DATA
    for data_name, data_data in yaml_data['outputs'].items():
        help_text += f"{data_data['label']}:\n\t{param_data['description']}\n"        
        
        file_extension = "json" if data_data['type'] in SPECIAL_TYPES else get_extension(data_data['type'])
        data_attrib = {"name": data_name,
                       "label": data_data['label'],
                       "format": file_extension
            }
    
        if data_data['type'].endswith("[]"):
            output_folder = data_name
            data_attrib['type'] = "list"
            output_replacements[data_name] = output_folder
            collection = ET.SubElement(outputs, "collection", data_attrib)
            discover_datasets = ET.SubElement(collection, "discover_datasets", {"directory": output_folder})
        else:
            output_path = data_name+"."+file_extension
            data_attrib['from_work_dir'] = output_path
            output_replacements[data_name] = output_path
            data = ET.SubElement(outputs, "data", data_attrib)
        
    
    # close the command
    command.text = rename_inputs_code + command.text
    galaxy_script_basename = "PUT_YOUR_SCRIPT_NAME_HERE"
    if galaxy_script_path is not None:
        galaxy_script_basename = os.path.basename(galaxy_script_path)
    elif biab_script_path is not None:
        galaxy_script_basename = os.path.basename(biab_script_path)
        
    # The script doesn't need arguments. It accesses the input by opening the input.json file created by data-formater.py
    command.text += f"&&\n{EXT_TO_INTERPRETER[script_ext]} '$__tool_directory__/{galaxy_script_basename}'"
    command.text = ET.CDATA(command.text)
        
    #HELP
    help_ = ET.SubElement(tool, 'help')
    help_.text = ET.CDATA(help_text)
    
    if biab_script_path is not None:
        #CONVERTING SCRIPT FILE
        #CREDENTIALS
        print("searching for environnement variables or credentials)")
        env_vars = script_processor.find_env_vars(biab_script_path)
        if env_vars:
            print(f"{len(env_vars)} found")
            credentials_attrib = {
                "name" : "env_vars",
                "version": "1.0",
                "label": "environnement variables",
                "description": "environnement variables including credentials"
                }
            
            credentials = ET.SubElement(requirements, 'credentials', credentials_attrib)
            for env_var in env_vars:
                credential_type = "secret" if env_var.endswith("_ID") or env_var.endswith("_PASSWORD") else "secret"
                secret_attrib = {
                    "name": env_var,
                    "inject_as_env": env_var,
                    "optional": "false",
                    "label": env_var.lower().replace("_", " "),
                    }
                secret = ET.SubElement(credentials, credential_type, secret_attrib)
    
    # WRITING XML FILE
    ET.indent(tool, space="  ")
    
    print(f"writing {os.path.basename(galaxy_wrapper_path)}")
    string_xml = ET.tostring(tool)
    with open(galaxy_wrapper_path, "wb") as xml_file:
        xml_file.write(string_xml)
        

def main():    
    parser = ArgumentParser(
        description ="This tool helps developpers port their bon in a box (biab) tools to galaxy.\n\
        It converts a biab yml wrapper file into a galaxy xml wrapper file, it also adapats the biab script to work into galaxy.\
        This tool doesn't manages all scenarios and the user's manual intervention will be needed to get a functional tool.")
    
    parser.add_argument(
        "-bw", "--biab_wrapper", 
        help="path of the Bon in a box tool's wrapper file.yml to be converted")
    
    parser.add_argument(
        "-bs", "--biab_script",
        help="path of the Bon in a box tool's script file to be converted")
    
    parser.add_argument(
        "-gw", "--galaxy_wrapper",
        help="path of the Bon in a box tool's wrapper file.yml to be saved")
    
    parser.add_argument(
        "-gs", "--galaxy_script",
        help="path of Galaxy tool's script file to be saved")
    
    parser.add_argument(
        "-s", "--shed",
        help="path of the .shed.yml file to be saved")
    
    parser.add_argument(
        "-g", "--galaxy",
        nargs='?',
        const="guess galaxy path",
        default=None,
        help="path to a galaxy instance. Use this to do the necessary changes to your instance to use the generated tools.\n\
        In addition to creating a script file and wrapper file it creates a .shed.yml file, add the tool to tool_conf.xml, generates the regions and countries data tables and add them tool_data_table_conf.xml\n\
        Make sure that the Galaxy path files you enter as arguments are in their expected locations.")
    
    args = parser.parse_args()
    
    biab_wrapper_path = args.biab_wrapper
    biab_script_path = args.biab_script
    galaxy_wrapper_path = args.galaxy_wrapper
    galaxy_script_path = args.galaxy_script
    shed_path = args.shed
    galaxy_path = args.galaxy
    
    if biab_wrapper_path is not None:
        yaml_data = get_yaml_data(galaxy_wrapper_path, biab_wrapper_path)
    
    if biab_script_path is not None:
        script_ext = Path(biab_script_path).suffix.lower()
        
        if script_ext not in EXT_TO_INTERPRETER:
            raise Exception("This converter only supports R, Python and Julia scripts, the extension of the script does not match any of them")
        
        match script_ext:
            case ".py":
                from . import py_converter as script_processor
            case ".r":
                from . import r_converter as script_processor
            case ".jl":
                from . import jl_converter as script_processor
    
    if galaxy_wrapper_path is not None:
        if biab_wrapper_path is None:
            raise Exception("the biab wrapper is required to generate the galaxy wrapper")
        generate_wrapper(script_processor, yaml_data, galaxy_wrapper_path, biab_script_path)
        
    if galaxy_script_path is not None:
        if biab_script_path is None:
            raise Exception("the biab script is required to generate the galaxy script")
        generate_script(script_processor, biab_script_path, galaxy_script_path, yaml_data)
    
    if shed_path is not None:
        if biab_wrapper_path is None:
            raise Exception("the biab wrapper is required to generate the .shed.yml file")
        generate_dot_shed(shed_path, yaml_data)
        
    if galaxy_path is not None:
        if biab_wrapper_path is None or biab_script_path is None:
            raise Exception("to test your tool in a galaxy instance you need a wrapper and a script")
        if galaxy_path == "guess galaxy path":
            reference_path = Path(biab_wrapper_path)
            print(f"guessing the path of the Galaxy instance is {reference_path.parent.parent.parent}")
        generate_data_tables(galaxy_path)
        add_tool_to_tool_conf(galaxy_path, galaxy_wrapper_path, galaxy_script_path)
        generate_dot_shed(Path(galaxy_script_path).parent.absolute() / ".shed.yml", yaml_data)
        
    print("Conversion complete")
        
    
if __name__ == "__main__":
    main()