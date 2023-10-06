from re import sub
from typing import Dict

from pretty import Color, paint

class WarningTracker:

    def __init__(self) -> None:
        
        self._old_db = {}
        self._new_db = {}
        self._active_db: Dict = None


    def set_db(self, dest: str) -> None:

        if dest == 'old':
            self._active_db = self._old_db
        elif dest == 'new':
            self._active_db = self._new_db
        else:
            raise NameError('Invalid name') # HACK

    
    def add(self, warning: str) -> None:

        db = self._active_db
        warning = sub(r':[0-9]+:', ':#:', warning)
        warning = sub(r':[0-9]+:', ':#:', warning)
        if warning in db:
            db[warning] += 1
        else:
            db[warning] = 1


    def get_diff(self) -> None:

        print(paint('\n[WARNINGS]', Color.SILVER))
        removed_db, added_db = {}, {}
        for warning, count in self._old_db.items():
            if warning in self._new_db:
                count_diff = self._new_db[warning] - count
            else:
                count_diff = -count
            if count_diff < 0:
                removed_db[warning] = -count_diff
            elif count_diff > 0:
                added_db[warning] = count_diff
        for warning, count in self._new_db.items():
            if warning not in self._old_db:
                added_db[warning] = count
        print('Removed:')
        for warning in removed_db:
            print(warning)
        print('Added:')
        for warning in added_db:
            print(warning)
            if added_db[warning] > 1:
                print(added_db[warning])
        print(f'{sum(removed_db.values())} warnings removed.')
        print(f'{sum(added_db.values())} warnings added.')
