import argparse
import semver
import xml.etree.ElementTree as ET


def bump_xml_version(xml_path):
    """
    Upgrade the version of given xml

    Args:
        xml_path (str): Path of the xml where the version need to be updated
    """
    # Parse XML
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Find the ExtensionBundleVersion attribute
    if 'ExtensionBundleVersion' in root.attrib:
        # Bump the version
        new_version = semver.bump_patch(root.attrib['ExtensionBundleVersion'])
        root.attrib['ExtensionBundleVersion'] = new_version

        # Write the XML
        tree.write(xml_path, encoding='UTF-8', xml_declaration=True)
        print(f'Updated ExtensionBundleVersion to {new_version}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bump XML Version')
    parser.add_argument('-p', '--xml-filepath', help='File to an XML file', type=str, required=True)
    args = vars(parser.parse_args())

    bump_xml_version(args["xml_filepath"])
