from collections import Counter
from pathlib import Path
from time import clock
import re

language_by_extension = {'.pyw': 'Python',
                          '.py': 'Python',
                          '.go': 'Go',
                          '.nim': 'Nimrod',
                          '.js': 'Javascript',
                          '.as': 'ActionScript',
                          '.java': 'Java'}

class Project(object):
    """
    Represents a single project and its files. May be refreshed for updated
    information.
    """
    EMPTY = 'empty'
    SINGLE_FILE = 'single file'
    MULTIPLE_FILES = 'multiple files'
    MODULE = 'module'

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.refresh()

    def refresh(self):
        """
        Updates the project properties by reading the newest version of the
        files. Potentially slow for large projects on slow disks.
        """
        self.ignored_patterns = self._get_git_ignore_patterns()
        self.files = []
        self._refresh_files(self.path)
        self.language = self._get_language()
        self.structure = self._get_structure()

        docs = self.path / 'docs'
        self.docs = docs if docs.exists() else None

    def _convert_glob_to_regex(self, glob_pattern):
        """
        Converts a path glob pattern (e.g. ".*/") into a regex (e.g. "\.*").

        This is useful because pathlib's implementation of match is orders of
        magnitude slower than a regex.

        Replacements may not be perfect.
        """
        regex = glob_pattern
        regex = regex.replace('.', r'\.') # Escape dots.
        regex = regex.replace('*', '.*')
        regex = regex.replace('+', r'\+') # Escape pluses
        regex = regex.replace('/', '') # Ignore slashes
        # Note glob patterns may have brackets, but they have the same
        # semantics as regex brackets, so we may keep them.
        return regex

    def _get_git_ignore_patterns(self):
        """
        Returns the compiled regex patterns from the gitignore file.
        """
        gitignore = self.path / '.gitignore'
        if not gitignore.exists():
            return

        with gitignore.open() as f:
            for line in filter(len, f.read().split('\n')):
                if not line.startswith('#'):
                    regex = self._convert_glob_to_regex(line)
                    yield re.compile(regex)

    def _get_language(self):
        if self.files:
            # All files are programming files, so we are guaranteed to find
            # some suffixes here.
            languages = Counter(language_by_extension[f.suffix]
                                for f in self.files)
            # most_common returns a list of tuples (item, count).
            return languages.most_common(1)[0][0]
        else:
            return 'Unknown'

    def _get_structure(self):
        """
        Identifies the project structure: empty (no files at all), module
        (files inside a module folder) or flat, which can be single or multiple
        file.
        """
        if len(self.files) == 0:
            return Project.EMPTY

        for f in self.files:
            if len(f.parts) > len(self.path.parts) + 1:
                return Project.MODULE

        if len(self.files) == 1:
            return Project.SINGLE_FILE
        else:
            return Project.MULTIPLE_FILES

    def _refresh_files(self, path):
        """
        Recursive function that appends the files found in `self.files`.
        """
        name = path.name

        # Ignore if hidden or temporary.
        if name.startswith('.') or name.startswith('__'):
            return

        # Ignore if in .gitignore. 
        for pattern in self.ignored_patterns:
            if pattern.match(name):
                return

        if path.is_file():
            if path.suffix in language_by_extension:
                self.files.append(path)
        else:
            for f in path.iterdir():
                self._refresh_files(f)

    def __repr__(self):
        return '{} ({})'.format(self.name, self.path)

class Workspace(object):
    """
    A workspace is a composed of projects.

    Can be used as an iterator ("for project in workspace: ...") or by project
    name ("workspace['news']").
    """
    def __init__(self, path):
        self.root = Path(path)
        self.dirs = {}
        for d in self.root.iterdir():
            if (d / '.git').is_dir():
                project = Project(d)
                self.dirs[project.name.lower()] = project

    def __getitem__(self, name):
        return self.dirs[name.lower()]

    def __iter__(self):
        return iter(self.dirs.values())

if __name__ == '__main__':
    workspace = Workspace(r'E:\projects')
    for project in workspace:
        print(project, project.language, project.docs)
    print('\n'.join(map(str, workspace['simplecrypto'].files)))
