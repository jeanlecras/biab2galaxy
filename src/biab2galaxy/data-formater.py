import json
import sys
import os

def generate_input_file(args):
    input_data = {}
    
    for i in range(1, len(args), 3):
        print("args", args)
        param_name, param_type, param_value = args[i:i+3]
        
        input_data[param_name] = {}

        if param_value == '': # value of optional parameters left empty
            input_data[param_name] = None
            
        else:
            match param_type:
                case "boolean":
                    input_data[param_name] = param_value=="true"
                    
                case "int":
                    input_data[param_name] = int(param_value)
                    
                case "float":
                    input_data[param_name] = float(param_value)
                    
                case "options[]":
                    input_data[param_name] = param_value.split(",")
                    
                case "text[]":
                    input_data[param_name] = param_value.split(",")
                    
                case "int[]":
                    input_data[param_name] = list(map(int, param_value.split(",")))
                    
                case "float[]":
                    input_data[param_name] = list(map(float, param_value.split(",")))
                
                case _: # including types text, options and mime
                    if not param_type.endswith("[]"):
                        input_data[param_name] = param_value
                    else:
                        collection = param_value.split(",")
                        collection.pop()
                        collection_path = os.path.abspath(param_name)
                        input_data[param_name] = [collection_path+"/"+element for element in collection]
                    
                
    with open("input.json", "w") as f:
        json.dump(input_data, f)


if __name__ == "__main__":
    print(sys.argv)
    generate_input_file(sys.argv)
