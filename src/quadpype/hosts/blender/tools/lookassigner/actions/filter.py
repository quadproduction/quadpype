from itertools import groupby


def valid_representations(representations):
    return [
        repre for repre in representations
        if repre.get('variant', None) and repre.get('version')
    ]


def last_version(representations):
    return sorted(representations, key=lambda x: x['version'], reverse=True)[0]


def identical_subsets(representations):
    representations_sorted = sorted(representations, key=lambda x: x["variant"])
    return [list(group) for _, group in groupby(representations_sorted, key=lambda x: x["variant"])]
