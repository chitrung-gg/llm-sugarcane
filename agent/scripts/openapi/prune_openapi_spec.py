import os
import yaml
import argparse
import sys

def get_all_refs(node, refs_set):
    """Recursively searches a dictionary/list for OpenAPI $ref keys and adds them to a set."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == '$ref' and isinstance(v, str):
                refs_set.add(v)
            else:
                get_all_refs(v, refs_set)
    elif isinstance(node, list):
        for item in node:
            get_all_refs(item, refs_set)

def prune_openapi_spec(input_yaml, output_yaml):
    # Load the original OpenAPI YAML file
    try:
        with open(input_yaml, 'r', encoding='utf-8') as file:
            spec = yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: The input file '{input_yaml}' was not found.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}")
        sys.exit(1)

    # Handle output path resolution
    if output_yaml is None:
        output_yaml = os.path.join(os.getcwd(), "output.yaml")

    if os.path.isdir(output_yaml):
        output_yaml = os.path.join(output_yaml, "output.yaml")

    # 1. Define the Absolute Paths whitelist
    ALLOWED_PATHS = {
        # Gene Searches
        '/gene/id/{gene_ids}/dataset_report',
        '/gene/symbol/{symbols}/taxon/{taxon}/dataset_report',
        '/gene/accession/{accessions}/dataset_report',
        '/gene/id/{gene_id}/orthologs',
        '/gene/locus_tag/{locus_tags}/dataset_report',
        '/gene/taxon/{taxon}/dataset_report',

        
        # Genome Searches
        '/genome/accession/{accessions}/dataset_report',
        '/genome/accession/{accessions}/annotation_report',
        '/genome/taxon/{taxons}/dataset_report',
        '/genome/assembly_name/{assembly_names}/dataset_report',
        '/genome/bioproject/{bioprojects}/dataset_report',
        '/genome/biosample/{biosample_ids}/dataset_report',

        
        # Taxonomy
        '/taxonomy/taxon/{taxons}/dataset_report',

        # BioSample
        '/biosample/accession/{accessions}/biosample_report'
    }
    
    paths_to_remove = []
    used_tags = set()

    print("--- STEP 1: STRICT PATH WHITELISTING ---")
    
    for path, path_item in list(spec.get('paths', {}).items()):
        # 1.a. If the path is not exactly in our whitelist, mark it for removal
        if path not in ALLOWED_PATHS:
            paths_to_remove.append(path)
            continue
            
        # 1.b. Even if allowed, scan for and remove deprecated HTTP operations
        operations_to_remove = []
        for method, operation in path_item.items():
            if isinstance(operation, dict):
                if operation.get('deprecated', False):
                    operations_to_remove.append(method)
                else:
                    # Collect tags from valid, allowed operations to clean up global tags later
                    tags = operation.get('tags', [])
                    used_tags.update(tags)
                    
        for method in operations_to_remove:
            del path_item[method]
            print(f"Removed deprecated operation: {method.upper()} {path}")
            
        # If a whitelisted path ended up empty (e.g., all its operations were deprecated)
        if len(path_item) == 0:
            paths_to_remove.append(path)

    # 2. Remove all non-whitelisted paths entirely
    for path in paths_to_remove:
        del spec['paths'][path]

    print(f"Kept exactly {len(spec.get('paths', {}))} absolute paths.")

    # 3. Clean up the global 'tags' list dynamically based on what's actually left
    if 'tags' in spec:
        spec['tags'] = [tag for tag in spec['tags'] if tag['name'] in used_tags]

    print("\n--- STEP 2: PRUNING ORPHANED COMPONENTS ---")
    # 4. Collect initial references from the remaining paths and global security elements
    used_refs = set()
    get_all_refs(spec.get('paths', {}), used_refs)
    get_all_refs(spec.get('security', []), used_refs)

    # 5. Recursively find nested references (Transitive Closure)
    components = spec.get('components', {})
    while True:
        start_count = len(used_refs)
        new_refs = set()
        
        for ref in used_refs:
            if ref.startswith('#/components/'):
                parts = ref.split('/')
                if len(parts) == 4:
                    comp_type = parts[2]
                    comp_name = parts[3]
                    
                    if comp_type in components and comp_name in components[comp_type]:
                        get_all_refs(components[comp_type][comp_name], new_refs)
        
        used_refs.update(new_refs)
        if len(used_refs) == start_count:
            break

    # 6. Delete any component that is not in the used_refs set
    removed_components_count = 0
    for comp_type, comp_dict in list(components.items()):
        if comp_type == 'securitySchemes':
            continue
            
        for comp_name in list(comp_dict.keys()):
            ref_str = f"#/components/{comp_type}/{comp_name}"
            if ref_str not in used_refs:
                del components[comp_type][comp_name]
                removed_components_count += 1
                
    print(f"Removed {removed_components_count} unused schemas/components.")

    # 7. Save the highly optimized specification to the output file
    try:
        with open(output_yaml, 'w', encoding='utf-8') as file:
            yaml.dump(spec, file, sort_keys=False, allow_unicode=True)
        print(f"\nSuccess! Whitelisted and fully pruned spec saved to: {output_yaml}")
    except IOError as e:
        print(f"Error writing to output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prune an OpenAPI file using a strict absolute path whitelist."
    )
    parser.add_argument(
        "-i", "--input", 
        required=True, 
        help="Path to the source OpenAPI YAML file"
    )
    parser.add_argument(
        "-o", "--output", 
        required=False, 
        help="Path where the pruned YAML file will be saved"
    )
    
    args = parser.parse_args()
    prune_openapi_spec(args.input, args.output)