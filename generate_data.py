"""
galaxy.web.framework.decorators ERROR 2026-06-16 14:33:37,406 [pN:main.1,p:11740,tN:WSGI_1] Uncaught exception in exposed API method:
Traceback (most recent call last):
  File "/home/pndb-cr/galaxy/lib/galaxy/web/framework/decorators.py", line 340, in decorator
    rval = func(self, trans, *args, **kwargs)
  File "/home/pndb-cr/galaxy/lib/galaxy/webapps/galaxy/api/tools.py", line 558, in build
    return tool.to_json(trans, kwd.get("inputs", kwd), history=history)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/__init__.py", line 3123, in to_json
    populate_state(request_context, self.inputs, params.__dict__, state_inputs, state_errors)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/__init__.py", line 444, in populate_state
    _populate_state_legacy(
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/__init__.py", line 575, in _populate_state_legacy
    state[input.name] = input.get_initial_value(request_context, context)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/grouping.py", line 820, in get_initial_value
    rval[child_input.name] = child_input.get_initial_value(trans, child_context)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/basic.py", line 1156, in get_initial_value
    options = cast(list[ParameterOption], self.get_options(trans, other_values))
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/basic.py", line 1002, in get_options
    return self.options.get_options(trans, other_values)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/dynamic_options.py", line 987, in get_options
    options = self.get_fields(trans, other_values)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/dynamic_options.py", line 840, in get_fields
    options = filter.filter_options(options, trans, other_values)
  File "/home/pndb-cr/galaxy/lib/galaxy/tools/parameters/dynamic_options.py", line 324, in filter_options
    if self.keep == (fields[self.column] in ref_values):
IndexError: list index out of range
"""

import duckdb
from pathlib import Path
import xml.etree.ElementTree as ET
from argparse import ArgumentParser

def parse_args():
    parser = ArgumentParser(
        description="Generates the data tables files required to use a bon in a box tool.\
            These tools often have a country and region parameter, these parameters are listss whose values come from the generated data tables\
            These tool also declares the data tables in to the tool_data_table_conf.xml.sample file"
        )
        
    parser.add_argument("galaxy_path", help="Path of the galaxy instance repository")
    args = parser.parse_args()
    galaxy_path = args.galaxy_path
    
    countries_path = Path(galaxy_path) / "tool-data" / "countries.loc"
    regions_path = Path(galaxy_path) / "tool-data" / "regions.loc"
    tool_data_conf_path = Path(galaxy_path) / "config" / "tool_data_table_conf.xml.sample"
    return countries_path, regions_path, tool_data_conf_path

###################
# GENERATING DATA #
###################
def generate_data(countries_path, regions_path):
    ddb = duckdb.connect()
    ddb.install_extension("spatial")
    ddb.load_extension("spatial")
    ddb.install_extension("httpfs")
    ddb.load_extension("httpfs")

    countries_parquet = "https://data.fieldmaps.io/adm0/osm/intl/adm0_polygons.parquet"
    regions_parquet = "https://data.fieldmaps.io/edge-matched/humanitarian/intl/adm1_polygons.parquet"
    
    print("querying data...")
    countries=ddb.sql("""
                      SELECT 
                          adm0_src as value, 
                          adm0_name as name
                      FROM read_parquet('%s')
                      WHERE adm0_src || adm0_name || geometry_bbox IS NOT NULL
                      """ % countries_parquet).df()
    countries.to_csv(countries_path, sep='\t', index=False)
    
    regions=ddb.sql("""
                    SELECT 
                        adm1_src as value, 
                        adm1_name as name
                    FROM read_parquet('%s')
                    WHERE adm1_src || adm1_name || adm0_src || adm0_name || geometry_bbox IS NOT NULL
                    """ % regions_parquet).df()
    regions.to_csv(regions_path, sep='\t', index=False)
    
    print("data successfully retrieved")
    
    with open(countries_path, "r") as f:
        header = f.readline()
        data = f.read()
    
    with open(countries_path, "w") as f:
        f.write("# " + header + data)
        
    
    with open(regions_path, "r") as f:
        header = f.readline()
        data = f.read()
    
    with open(regions_path, "w") as f:
        f.write("# " + header + data)
    

#############################
# DECLARING FILES IN CONFIG #
#############################

def declare_tables(tool_data_conf_path):
    print("declaring data tables to tool_data_table_conf.xml...")
    tree = ET.parse(tool_data_conf_path)
    root = tree.getroot()
    
    existing = {t.get("name") for t in root.findall("table")}
    
    # Definition of tables to add if missing
    missing_tables = []
    
    if "regions" not in existing:
        regions = ET.fromstring(
            '<table name="regions" comment_char="#" allow_duplicate_entries="False">\n'
            '        <columns>value, name</columns>\n'
            '        <file path="tool-data/regions.loc" />\n'
            '    </table>'
        )
        missing_tables.append(("regions", regions))
    
    if "countries" not in existing:
        countries = ET.fromstring(
            '<table name="countries" comment_char="#" allow_duplicate_entries="False">\n'
            '        <columns>value, name</columns>\n'
            '        <file path="tool-data/countries.loc" />\n'
            '    </table>'
        )
        missing_tables.append(("countries", countries))
    
    if not missing_tables:
        print("The data tables'regions' and 'countries' already exist. No modification.")
    else:
        for name, element in missing_tables:
            root.append(element)
            print(f"Data table '{name}' added.")
    
    ET.indent(tree, space="    ")
    tree.write(tool_data_conf_path, encoding="unicode", xml_declaration=True)
    print(f"File saved : {tool_data_conf_path}")

if __name__ == "__main__":
    countries_path, regions_path, tool_data_conf_path = parse_args()
    generate_data(countries_path, regions_path)
    declare_tables(tool_data_conf_path)