import argparse
import semver
import xml.etree.ElementTree as ET


def upgrade_xml_version(xml_path):
    """
    Upgrade the version of given xml

    Args:
        xml_path (str): Path of the xml where the vesion need to be updated
    """
    # parse XML
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


parser = argparse.ArgumentParser(description='Generating ZXP Process')
parser.add_argument('-u', '--upgrade-xml-version', help='Upgrade Version', type=str, required=True)
args = vars(parser.parse_args())

if args["upgrade_xml_version"]:
    upgrade_xml_version(args["upgrade_xml_version"])
