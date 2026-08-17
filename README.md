# Bon in a box to Galaxy tool converter

[Bon in a box](https://boninabox.geobon.org/) and [Galaxy](https://usegalaxy.org/) are two platforms for building and sharing scientific workflows. This tool helps developers migrate Biab tools to Galaxy by automating part of the process. This tool doesn't handle every scenario, manual intervention is needed to get a functionning tool.

## Features
- Generation of Galaxy wrapper file based on Biab wrapper file
    - Generation of a Cheetah command
    - Generation of input parameters
    - Generation of output data and collecions
    - Managing requirements
- Creation of modified Biab script adapted to Galaxy
    - Rewriting Biab dependant functions
    - Deadling with Biab special types (bbox, CRS, country, region...)
    - Detecting credentials variables
- Adding a converted tool to the Galaxy's list of tools
- Generation of a .shed.yml file

## Requirements

- local Galaxy instance (highly recommended)
- python 3.12+

Installation:
```
pip install biab2galaxy
```

## Usage

```
biab2galaxy [OPTIONS]
```
 
### Options
 
| Flag | Description |
|---|---|
| `-bw`, `--biab_wrapper` | Path of the BiaB tool's wrapper file (`.yml`) to be converted. |
| `-bs`, `--biab_script` | Path of the BiaB tool's script file to be converted. |
| `-gw`, `--galaxy_wrapper` | Path where the generated Galaxy wrapper file (`.xml`) should be saved. |
| `-gs`, `--galaxy_script` | Path where the generated Galaxy script file should be saved. |
| `-s`, `--shed` | Path where the `.shed.yml` file should be saved. |
| `-g`, `--galaxy` [`PATH`] | Path to a Galaxy instance. Applies the necessary changes to that instance to use the generated tool (adds it to `tool_conf.xml` and generates a `.shed.yml`). If used without a value, the Galaxy instance path is guessed automatically. |
 
Supported script languages: **Python** (`.py`), **R** (`.R`).
 
### Requirements
 
- `--biab_wrapper` is required to generate the Galaxy wrapper (`--galaxy_wrapper`) or the `.shed.yml` file (`--shed`).
- `--biab_script` is required to generate the Galaxy script (`--galaxy_script`).
- `--biab_wrapper` and `--biab_script` are both required to use `--galaxy`.
### Examples
 
Convert a BiaB wrapper to a Galaxy wrapper:
```bash
biab2galaxy -bw tool.yml -bs tool.py -gw tool.xml
```
 
Convert both the wrapper and the script:
```bash
biab2galaxy -bw tool.yml -bs tool.py -gw tool.xml -gs tool.py
```
 
Generate a `.shed.yml` file alongside the wrapper:
```bash
biab2galaxy -bw tool.yml -bs tool.py -gw tool.xml -gs tool.py -s .shed.yml
```
 
Convert a tool and deploy it directly into a Galaxy instance:
```bash
biab2galaxy -bw tool.yml -bs tool.py -gw tool.xml -gs tool.py -g /path/to/galaxy
```
 
Same as above, but let the tool guess the Galaxy instance path from `--galaxy_script`:
```bash
biab2galaxy -bw tool.yml -bs tool.py -gw tool.xml -gs tool.py -g
```

## Recommendations

Check the [drafts of converted tools](https://github.com/jeanlecras/biab-tools-converted-to-galaxy), you might find what you are looking for, if not you can contribute to it.

Review the file at ```~/.config/biab2galaxy/type_to_extension.json``` to set which file extension corresponds to each MIME type.

## What this converter can't do
- Generate tests for the converted tools
- Generate an appropriate tool description
- Differentiate optional and required parameters
- Find extension(s) for any Biab (MIME) type

## Missing features
- Handling of data_collection in outputs
- Validator to check if the bounding box coordinates are valid (ex: xmin < xmax, ymin < ymax)
- Julia scripts support
- Fixed versions for default R dependencies
- Fixed versions given to dependencies with no specified version
- Robust R parser (the current one is based on regex)
- Exhaustive mapping of file extensions to MIME types
