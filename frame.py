import json

from main_data import MainData
from side_info import SideInfo


class Frame(object):
    """
    Frame : container for all frame things and decoded PCM.
    """

    def __init__(self, main_data: MainData):
        self.header = main_data.header
        self.side_info = main_data.side_info
        self.main_data = main_data

    def __str__(self):
        return json.dumps({
            'header': str(self.header),
            'side_info': str(self.side_info),
            'main_data': str(self.main_data),
        }).replace('"', '')
