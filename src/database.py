from typing import Dict, List

class Data:

    class BuildData:

        def __init__(self: int) -> None:
            self.id
            self.tests
            self.firmwares
            self.time
            self.pc
            self.path
            self.commit_hash
            self.tree_hash
            self.name


    def __init__(self) -> None:
        self.commit_to_tree: Dict[int, List[int]] = {}
        self.tree_to_commit: Dict[int, int] = {}
        self.build_data_list: List[self.BuildData] = []
        self.current_build_data: self.BuildData
    
