import argparse
import semver
import xml.etree.ElementTree as ET
from xml.etree import ElementTree


class CommentedTreeBuilder(ElementTree.TreeBuilder):
    """ This class will retain remarks and comments"""
    def comment(self, data):
        self.start(ElementTree.Comment, {})
        self.data(data)
        self.end(ElementTree.Comment)


def bump_xml_version(xml_path):
    """
    Upgrade the version of given xml

    Args:
        xml_path (str): Path of the xml where the version need to be updated
    """
    # Parse XML
    ctb = CommentedTreeBuilder()
    tree = ET.parse(xml_path, parser=ET.XMLParser(target=ctb))
    root = tree.getroot()

    # Find the ExtensionBundleVersion attribute
    if 'ExtensionBundleVersion' in root.attrib:
        # Bump the version
        new_version = semver.bump_patch(root.attrib['ExtensionBundleVersion'])
        root.attrib['ExtensionBundleVersion'] = new_version

        # Write the XML
        file_content = ET.tostring(root, encoding='UTF-8', xml_declaration=True)
        file_content = file_content.replace(b"\r\n", b"\n")
        with open(xml_path, 'wb') as open_file:
            open_file.write(file_content)

        print(f'Updated ExtensionBundleVersion to {new_version}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bump XML Version')
    parser.add_argument('-p', '--xml-filepath', help='File to an XML file', type=str, required=True)
    args = vars(parser.parse_args())

    bump_xml_version(args["xml_filepath"])
