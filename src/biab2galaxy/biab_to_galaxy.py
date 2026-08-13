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


def get_user_data_path():
    config_dir = Path(user_config_dir("biab2galaxy"))
    config_dir.mkdir(parents=True, exist_ok=True)
    user_file = config_dir / "type_to_extension.json"

    if not user_file.exists():
        default_file = files("biab2galaxy").joinpath("type_to_extension.json")
        shutil.copy(default_file, user_file)

    return user_file

def main():
    parser = ArgumentParser(
        description ="This tool helps developpers port their bon in a box (biab) tools to galaxy.\n\
        It converts a biab yml wrapper file into a galaxy xml wrapper file, it also adapats the biab script to work into galaxy.\
        This tool doesn't manages all scenarios and the user's manual intervention will be needed to get a functional tool.\
        "
        )
    
    parser.add_argument(
        "biab_wrapper", 
        help="path of the Bon in a box tool's wrapper file.yml to be converted",
        )
    
    parser.add_argument(
        "biab_script",
        help="path of the Bon in a box tool's script file to be converted",
        )
    
    parser.add_argument(
        "galaxy_wrapper",
        help="path of the Bon in a box tool's wrapper file.yml to be saved",
        )
    
    parser.add_argument(
        "galaxy_script",
        help="path of Galaxy tool's script file to be saved",
        )
    
    parser.add_argument(
        '-g', '--galaxy-instance',
        help="path to a galaxy instance. Use this to do the necessary changes to your instance to use the generated tools.\n\
        In addition to creating a script file and wrapper file it creates a .shed.yml file, add the tool to tool_conf.xml, generates the regions and countries data tables and add them tool_data_table_conf.xml\n\
        Make sure that the Galaxy path files you enter as arguments are in their expected locations.")
    
    args = parser.parse_args()
    input_wrapper = args.biab_wrapper
    output_wrapper = args.galaxy_wrapper
    biab_script_path = args.biab_script
    galaxy_script_path = args.galaxy_script
    shed_path = Path(galaxy_script_path).parent.absolute() / ".shed.yml"
    main_script_name = os.path.basename(galaxy_script_path)
    galaxy_script_dir = os.path.dirname(galaxy_script_path)
    os.makedirs(galaxy_script_dir, exist_ok=True)
    shutil.copy(biab_script_path, galaxy_script_path)
    
    in_glx_instance = args.galaxy_instance is not None
    galaxy_path = args.galaxy_instance
    
    ##########################
    # GENERATING DATA TABLES #
    ##########################
    
    if in_glx_instance:
        tool_data_conf_path = Path(galaxy_path) / "config" / "tool_data_table_conf.xml.sample"
        regions_path = Path(galaxy_path) / "tool-data" / "regions.loc"
        countries_path = Path(galaxy_path) / "tool-data" / "countries.loc"
        if not (os.path.isfile(regions_path) and os.path.isfile(countries_path)):
            generate_data(countries_path, regions_path)
            declare_tables(tool_data_conf_path)
        else:
            print("regions and countries data tables already present")
    
    ######################
    # DETECTING LANGUAGE #
    ######################
    
    EXT_TO_INTERPRETER = {
        "jl": "julia",
        "r": "Rscript",
        "py": "python"
        }
    
    script_ext = main_script_name.split(".")[-1].lower()
    
    if script_ext not in EXT_TO_INTERPRETER:
        raise Exception("This converter only supports R, Python and Julia scripts, the extension of the script does not match any of them")
    
    match script_ext:
        case "py":
            from . import py_converter as script_processor
        case "r":
            from . import r_converter as script_processor
        case "jl":
            from . import jl_converter as script_processor
    
    #################
    # LOADING files #
    #################
    
    interpreter = EXT_TO_INTERPRETER[script_ext]
    
    print("reading biab .yml wrapper")
    with open(input_wrapper) as yaml_file:
        try:
            yaml_data = yaml.safe_load(yaml_file)
        except yaml.YAMLError:
            raise RuntimeError(f"error while reading biab wrapper {input_wrapper}")
            
    # opens a dictionnary mapping MIME types to file extensions.
    # Biab uses MIME types to describe files, Galaxy uses extension (format="...")
    user_data_path = get_user_data_path()
    with open(user_data_path, "r") as file:
        file_str = file.read()
        TYPE_TO_EXTENSION = json.loads(file_str)
    
    ##########################
    # BUILDING DOT_SHED FILE #
    ##########################
    
    dot_shed = {
        "name": yaml_data['name'],
        "owner": yaml_data['author'][0]['name'],
        "description": yaml_data['description'],
        "homepage_url": yaml_data['author'][0]['identifier'],
        "long_description": yaml_data['description'],
        "type": "unrestricted",
        "categories": [],
        "auto_tool_repositories": [{
            "name_template": "{{ tool_id }}",
            "description_template": yaml_data['name']+": {{ tool_id }}"
            }]
        }
    
    print("writing .shed.yml file")
    with open(shed_path, "w") as file:
        yaml.dump(dot_shed, file)
    
        
    ################################
    # ADDING TOOL TO tool_conf.xml #
    ################################
    
    if in_glx_instance:
        print("adding the tool to the tool_conf file")
        tool_conf_path = Path(galaxy_path) / "config" / "tool_conf.xml.sample"
        tool_conf = ET.parse(tool_conf_path)
        toolbox = tool_conf.getroot()
         
        section_attrib = {'id': 'biab', 'name': 'biab'}
        section = toolbox.findall('section')[-1]
        if section.get('id') != "biab":
            section = ET.SubElement(toolbox, 'section', section_attrib)
        
        # path of the galaxy script file including its parent directory
        path_of_galaxy_script = Path(output_wrapper)
        file_attr = str(Path(*path_of_galaxy_script.parts[-2:]))
        print("file_attr", file_attr)
        
        existing_tool = None
        for tool_line in section.findall('tool'):
            if tool_line.get('file') == file_attr:
                existing_tool = tool_line
                break
        
        if existing_tool is None:
            tool_ine = ET.SubElement(section, 'tool', {"file": file_attr})
        
        tool_conf.write(tool_conf_path, encoding='utf-8', xml_declaration=True)
        
        #copy data-formater.py to to the galaxy tool directory
        project_dir = os.path.dirname(os.path.abspath(__file__))
        shutil.copy2(Path(project_dir) / "data-formater.py", Path(galaxy_script_dir) / "data-formater.py")
        
        
    
    ###########################
    # BUILDING FILE STRUCTURE #
    ###########################
    
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
    
    SPECIAL_TYPES = {"country", "countryRegion", "countryRegionCRS", "CRS", "bboxCRS"}
    
    
    def add_options(parent: ET.Element, options_list: iter) -> list[ET.Element]:
        for option_name in yaml_options:
            option = ET.SubElement(parent, 'option', {"value":option_name})
            option.text = option_name
            
    def get_extension(yaml_type):
        base_type = yaml_type
        if yaml_type.endswith("[]"):
            base_type = yaml_type[:-2]
        if base_type in TYPE_TO_EXTENSION:
            print(f"searching extensions for {yaml_type} type")
            return TYPE_TO_EXTENSION[base_type]
        else:
            warn(f"No extension found for type {base_type}, consider adding it to type_to_extension.json")
            return ""
            
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
            add_options(param, yaml_options)
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
    output_replacements = {}
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
    # The script doesn't need arguments. It accesses the input by opening the input.json file created by data-formater.py
    command.text += f"&&\n{EXT_TO_INTERPRETER[script_ext]} '$__tool_directory__/{main_script_name}'"
    command.text = ET.CDATA(command.text)
        
    #HELP
    help_ = ET.SubElement(tool, 'help')
    help_.text = ET.CDATA(help_text)
    
    
    ####################
    # WRITING XML FILE #
    ####################
    ET.indent(tool, space="  ")
    
    print(f"writing {os.path.basename(output_wrapper)}")
    string_xml = ET.tostring(tool)
    with open(output_wrapper, "wb") as xml_file:
        xml_file.write(string_xml)
        
        
    ##########################
    # CONVERTING SCRIPT FILE #
    ##########################
    
    print(f"adapting {os.path.basename(biab_script_path)}")
    print("\treplacing biab dedicated functions")
    script_processor.replace_biab_functions(galaxy_script_path)
    print("\tadding inputs handling")
    # rewrites biab_input function, replace it by the reading of input.json
    script_processor.add_inputs_handling(galaxy_script_path)
    print("\tadding outputs handling")
    # rewrites biab_output function, replace it by a rename to a predictable filename
    script_processor.add_outputs_handling(galaxy_script_path, output_replacements)
    
if __name__ == "__main__":
    main()