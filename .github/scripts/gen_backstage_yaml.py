from typing import Dict, List, Tuple
from os import path, mkdir
import textwrap
import yaml
import re

from adi_doctools.typing.hdl import Library, Project
from adi_doctools.cli.hdl_gen import makefile_pre

dir_: str = "backstage_yaml"
doc_link: str = 'https://analogdevicesinc.github.io/hdl'
link_entry_: str = 'https://github.com/analogdevicesinc/hdl/tree/main'
source_location: str = 'https://github.com/analogdevicesinc/hdl/tree/main'
loc_url: str = "https://github.com/analogdevicesinc/hdl/tree/backstage_yaml"
targets: List = []
link_entry: Dict = {
    'url': None,
    'title': 'Source code',
    'icon': 'web'
}

link_entry_doc: Dict = {
    'url': None,
    'title': 'Documentation',
    'icon': 'web'
}

delimeters = ('===', '---', '~~~', '^^^', '"""', "'''")

vendor = {
    'xilinx': "AMD Xilinx",
    'intel': "Intel Altera",
    'lattice': "Lattice"
}


def yaml_template() -> dict:
    return {
        'apiVersion': 'backstage.io/v1alpha1',
        'kind': 'Component',
        'metadata': {
            'name': None,
            'title': None,
            'description': None,
            'version': None,
            'classification': 'software',
            'license': ['ADI BSD License'],
            'annotations': {
                'backstage.io/source-location': None
            },
            'tags': ['hdl'],
            'links': []
        },
        'spec': {
            'owner': 'group:default/hdl-sw-team',
            'type': 'source',
            'lifecycle': 'sustain'
            # For versioned components, add 'subcomponentOf'
        }
    }


def get_description_parts(
    desc: List[str]
) -> Tuple[str, List[str]]:
    desc = [de.strip()+'\n' for de in desc]
    desc = ''.join(desc)
    # Grab ADI role part name without text
    r0 = r"(:adi:`)([^<>:]+?)(`)"
    # Pop roles without text
    r2 = r'(:\S+?:`)([^<>:]+?)(`)'

    # Grab ADI role part name with text
    r1 = r'(:adi:`)([^<]+?)( <)([^:>]+?)(>)(`)'
    # Pop roles with text
    r3 = r'(:\S+?:`)([^<]+?)( <)([^:>]+?)(>)(`)'

    parts = set()
    for m in re.finditer(r0, desc):
        if not ('/' in m.group(2)):
            parts.add(m.group(2).lower())
    desc = re.sub(r2, r'\2', desc)

    for m in re.finditer(r1, desc):
        if not ('/' in m.group(4)):
            parts.add(m.group(4).lower())
    desc = re.sub(r3, r'\2', desc)
    desc = desc.replace('`', '').replace('*', '')

    # Re-fold at column 80 since some content overflows
    # and also to compensate by the removed roles
    desc = desc.replace('. ', '.\\n')
    desc = desc.replace('\n\n', '\\n\\n')
    desc = desc.replace('\n', ' ')
    desc = desc.replace('\\n', '\n')
    desc = desc.split('\n')
    desc = [textwrap.fill(des, width=80) for des in desc]
    desc = '\n'.join(desc)

    return desc, list(parts)


def get_description(
    data: List[str]
) -> List[str]:
    desc = []
    directive_lock = False
    for d in data:
        if d.startswith(delimeters):
            break
        elif d.startswith(".. "):
            directive_lock = True
            continue
        elif directive_lock:
            if not (d.startswith("   ") or d == "\n"):
                directive_lock = False
            else:
                continue
        desc.append(d)
    desc.pop()
    desc.pop()
    return desc


def get_description_library(
    file: str
) -> Tuple[List[str], List[str], str]:
    """
    Get the first paragraph of a project index file.
    Accepts
    ::

       Libray name
       ============
    """
    with open(file) as f:
        data = f.readlines()

    index = -1
    for i, d in enumerate(data):
        if d.startswith("==="):
            index = i+2
            break

    if index == -1:
        return [], []

    title = data[index-3][:-1]
    data = data[index:]
    desc = get_description(data)

    return *get_description_parts(desc), title


def get_description_project(
    file: str
) -> Tuple[List[str], List[str]]:
    """
    Get the first paragraph of a project index file.
    Accepts both
    ::

       Project name
       ============
    and
    ::

       Project name
       ============

       Overview
       --------
    """
    with open(file) as f:
        data = f.readlines()

    index = -1
    for i, d in enumerate(data):
        if d.startswith("==="):
            index = i+2
            break

    if index == -1:
        return [], []

    title = data[index-3][:-1]

    if "Overview\n" in data:
        index = data.index("Overview\n")+3

    data = data[index:]
    desc = get_description(data)

    return *get_description_parts(desc), title


def write_hdl_library_yaml(
    library: Library,
    key: str
) -> None:
    key_ = key.replace('/', '-')
    t: Dict = yaml_template()
    m = t['metadata']
    a = m['annotations']
    m['name'] = f"hdl-library-{key_}"
    m['title'] = f"{library['name'].upper()} HDL IP core"
    m['version'] = 'main'
    a['backstage.io/source-location'] = f'url:{source_location}/library/{key}'
    m['tags'].extend(['library', 'ip-core'])
    link_entry['url'] = f"{link_entry_}/library/{key}"
    m['links'].append(link_entry)
    tags_ = None
    file1 = path.join('docs', 'library', key, 'index.rst')
    file2 = path.join('docs', 'library', key+'.rst')
    if path.isfile(file1):
        link_entry_doc['url'] = f"{doc_link}/library/{key}/index.html"
        m['links'].append(link_entry_doc)
        m['description'], tags_, title = get_description_library(file1)
    elif path.isfile(file2):
        link_entry_doc['url'] = f"{doc_link}/library/{key}.html"
        m['links'].append(link_entry_doc)
        m['description'], tags_, title = get_description_library(file2)
    if tags_:
        m['tags'].extend(tags_)
        m['title'] = title + " HDL IP core"
    m['tags'].sort()

    if key.startswith('jesd204'):
        m['license'].append('ADIJESD204')
    elif key.startswith('corundum'):
        m['license'].append('BSD-2-Clause-Views')

    for v in library['vendor']:
        ld = library['vendor'][v]['library_dependencies']
        if len(ld) > 0:
            depends_on = [f"hdl-library-{ld_.replace('/', '-')}" for ld_ in ld]
            if 'depends_on' not in t['spec']:
                t['spec']['dependsOn']: List = []
            t['spec']['dependsOn'].extend(depends_on)

    targets.append(f"{loc_url}/library-{key_}-catalog-info.yaml")

    if m['description'] is None:
        m['description'] = m['title']

    file = path.join(dir_, f"library-{key_}-catalog-info.yaml")
    with open(file, 'w', encoding='utf-8') as f:
        yaml.dump(t, f, default_flow_style=False, allow_unicode=True)


def write_hdl_project_yaml(
    project: Project,
    key: str
) -> None:
    key_ = key.replace('/', '-')
    t: Dict = yaml_template()
    m = t['metadata']
    a = m['annotations']
    m['name'] = f"hdl-project-{key_}"
    m['title'] = f"{project['name'].upper()} HDL project"
    m['version'] = 'main'
    a['backstage.io/source-location'] = f'url:{source_location}/projects/{key}'
    m['tags'].extend(['project', 'reference-design'])
    if key.startswith('common'):
        m['tags'].append('template')
    link_entry['url'] = f"{link_entry_}/projects/{key}"
    if key.startswith('common'):
        m['description'] = "Template project."
    m['links'].append(link_entry)

    tags_ = None
    key__ = key[:key.find('/')] if '/' in key else key
    key___ = key[key.find('/')+1:] if '/' in key else None
    file1 = path.join('docs', 'projects', key__, 'index.rst')
    file2 = path.join('docs', 'projects', key__+'.rst')
    if path.isfile(file1):
        link_entry_doc['url'] = f"{doc_link}/projects/{key__}/index.html"
        m['links'].append(link_entry_doc)
        m['description'], tags_, title = get_description_project(file1)
    elif path.isfile(file2):
        link_entry_doc['url'] = f"{doc_link}/projects/{key__}.html"
        m['links'].append(link_entry_doc)
        m['description'], tags_, title = get_description_project(file2)
    if tags_:
        m['tags'].extend(tags_)
        m['title'] = title
    if key___ is not None:
        m['tags'].append(key___)

    targets.append(f"{loc_url}/project-{key_}-catalog-info.yaml")
    if len(project['lib_deps']) > 0:
        depends_on = [f"hdl-library-{ld_.replace('/', '-')}"
                      for ld_ in project['lib_deps']]
        t['spec']['dependsOn'] = depends_on

    if m['description'] is None:
        m['description'] = m['title']
    elif key___ is not None:
        m['description'] += ("\nIt targets the "
                             f"{vendor[project['vendor']]} "
                             f"{key___.upper()}.")
    m['tags'].sort()

    file = path.join(dir_, f"project-{key_}-catalog-info.yaml")
    with open(file, 'w', encoding='utf-8') as f:
        yaml.dump(t, f, default_flow_style=False, allow_unicode=True)


def write_hdl_locations_yaml(
    library: Dict[str, Library],
    project: Dict[str, Project]
) -> None:
    """
    Generate locations.yaml
    """
    with open(path.join(dir_, 'locations.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump({
            'apiVersion': 'backstage.io/v1alpha1',
            'kind': 'Location',
            'metadata': {
                'name': 'hdl-location'
            },
            'spec': {
                'owner': 'group:default/hdl-sw-team',
                'type': 'url',
                'targets': targets
            }
        }, f)


def str_presenter(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str',
                                       data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def main():
    yaml.add_representer(str, str_presenter)

    if not path.isdir(dir_):
        mkdir(dir_)

    project, library = makefile_pre()

    for key in library:
        write_hdl_library_yaml(library[key], key)

    for key in project:
        write_hdl_project_yaml(project[key], key)

    write_hdl_locations_yaml(library, project)


if __name__ == '__main__':
    """
    Run from repo root.
    """
    main()
