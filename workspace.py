from collections import Counter
from pathlib import Path
from time import clock, time
import re
from subprocess import check_output

language_by_extension = {'.pyw': 'Python',
                          '.py': 'Python',
                          '.go': 'Go',
                          '.nim': 'Nimrod',
                          '.js': 'Javascript',
                          '.as': 'ActionScript',
                          '.java': 'Java'}

class GitRepository(object):
    """
    Class for tracking Git repo information.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.refresh()

    def refresh(self):
        """
        Refreshes the repository stats, such as dirtiness, age, number of
        commits ahead of origin and total commit count.
        """
        self.behind = None

        self.is_dirty = len(self.git('status --porcelain')) > 0
        self.age = time() - int(self.regit('log --format=%at"', r'^(\d+)'))
        self.ahead = self.regit('status -b --porcelain',
                                r'\[ahead (\d+)\]\n', int) or 0
        self.behind = self.regit('status -b --porcelain',
                                 r'\[behind (\d+)\]\n', int) or 0
        self.commit_count = sum(int(p.split()[0]) # "total username\n"
                                for p in self.git('shortlog -s').splitlines())

    def refresh_remote(self):
        """
        Fetches the latests version of the origin branch, if one exists.
        Because this is a network operation expect large delays.
        """
        has_remote = 'origin' in self.git('remote')
        if has_remote:
            self.git('fetch')
            # Update number of commits ahead or behind.
            self.refresh()

    def regit(self, command, pattern, transformation=lambda x: x):
        """
        Runs a git command and returns a value extracted from the output. If no
        value matches the expected pattern, None is returned.
        Optionally takes a transformation function that is used to convert the
        value if it exists.
        """
        result = self.git(command)
        match = re.search(pattern, result)
        return transformation(match.groups()[0]) if match else None

    def git(self, command):
        """
        Runs a git command on this repository, returning the output.

        Wildly unsafe, do not expose to untrusted input.
        """
        template = 'git --git-dir="{}" --work-tree="{}" {}'
        full_command = template.format(self.path / '.git', self.path, command)
        return check_output(full_command, shell=True).decode('utf-8')

    def __repr__(self):
        if self.behind or self.ahead:
            return '{}{} commits [+{}|-{}]'.format('*' if self.is_dirty else '',
                                                   self.commit_count,
                                                   self.ahead,
                                                   self.behind)
        else:
            return '{}{} commits'.format('*' if self.is_dirty else '',
                                         self.commit_count)


class Package(object):
    """
    Represents a (currently Python-only) distributable package. Must have a
    setup file and possibly a CHANGES.txt one.
    
    Extracts information like version.
    """
    def __init__(self, setup_file, repo):
        self.setup = setup_file
        self.repo = repo

        changes_file = setup_file.parent / 'CHANGES.txt'

        if changes_file.exists():
            self._refresh_from_changes(changes_file)
        else:
            self.changes = None
            self.version = None
            self.age = None
            self.unpublished_commits = None

    def _refresh_from_changes(self, changes_file):
        self.changes = changes_file
        self.last_version_date = self.changes.stat().st_mtime
        self.age = time() - self.last_version_date

        git_parameters_template = 'log --oneline --since={}'
        git_parameters = git_parameters_template.format(self.last_version_date)
        self.unpublished_commits = list(filter(len,
                                    self.repo.git(git_parameters).split('\n')))

        with self.changes.open() as changes_text:
            self.version = changes_text.read().split()[0]

    def __repr__(self):
        unpublished = self.unpublished_commits and len(self.unpublished_commits)
        if not unpublished:
            template = 'v{version} ({age})'
        elif unpublished == 1:
            template = 'v{version} ({age}, 1 commit behind)'
        else:
            template = 'v{version} ({age}, {unpublished} commits behind)'

        return template.format(version=self.version,
                               age=pretty_seconds(self.age),
                               unpublished=unpublished)


class Files(object):
    """
    Represents the files of a project. Includes list of all file paths and
    statistics about their size.
    """
    def __init__(self, root):
        self.root = root
        self.refresh()

    def __len__(self):
        return len(self._files)

    def __iter__(self):
        return iter(self._files)

    def __getitem__(self, index):
        return self._files[index]

    def refresh(self):
        """
        Updates the stats by reading all files.
        """
        self.ignored_patterns = self._get_git_ignore_patterns()
        self._files = []
        self._refresh_files(self.root)
        self.structure = self._get_structure()
        self.sloc, self.largest_file = self._get_size_info()

    def _refresh_files(self, path):
        """
        Recursive function that appends the files found to `self._files`.
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
                self._files.append(path)
        else:
            for f in path.iterdir():
                self._refresh_files(f)

    def _get_size_info(self):
        """
        Returns a count of all lines in all files in this project, and the path
        of the largest file.
        """
        sloc = 0
        largest_file_size = 0
        largest_file = None
        for file_path in self._files:
            with file_path.open(encoding='utf-8') as f:
                file_size = sum(1 for line in f)
                sloc += file_size

                if file_size > largest_file_size:
                    largest_file_size = file_size
                    largest_file = file_path

        return sloc, largest_file

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
        gitignore = self.root / '.gitignore'
        if not gitignore.exists():
            return

        with gitignore.open() as f:
            for line in filter(len, f.read().split('\n')):
                if not line.startswith('#'):
                    regex = self._convert_glob_to_regex(line)
                    yield re.compile(regex)

    def _get_structure(self):
        """
        Identifies the project structure: empty (no files at all), module
        (files inside a module folder) or flat, which can be single or multiple
        file.
        """
        if len(self._files) == 0:
            return Project.EMPTY

        for f in self._files:
            if len(f.parts) > len(self.root.parts) + 1:
                return Project.MODULE

        if len(self._files) == 1:
            return Project.SINGLE_FILE
        else:
            return Project.MULTIPLE_FILES


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

    @property
    def repo(self):
        """
        Returns an up-to-date GitRepository object with information about the
        version control system of this project. Potentially slow to gather the
        information.
        """
        if self._repo is None:
            self._repo = GitRepository(self.path)
        return self._repo

    @property
    def files(self):
        """
        Returns an up-to-date object listing the project's files and their
        attributes. Potentially slow for large projects.
        """
        if self._files is None:
            self._files = Files(self.path)
        return self._files


    def refresh(self):
        """
        Updates the project properties by reading the newest version of the
        files. Potentially slow for large projects on slow disks.
        """
        self._repo = None
        self._files = None

        self.language = self._get_language()

        docs = self.path / 'docs'
        self.docs = docs if docs.exists() else None

        readmes = list(self.path.glob('README.*'))
        self.readme = readmes[0] if readmes else None

        package_file = self.path / 'setup.py'
        self.package = Package(package_file, self.repo) if package_file.exists() else None

    def _get_language(self):
        languages = Counter(language_by_extension[f.suffix]
                            for f in self.path.iterdir()
                            if f.suffix in language_by_extension)
        if len(languages) == 0:
            return 'Unknown'
        else:
            # most_common returns a list of tuples (item, count).
            return languages.most_common(1)[0][0]

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

    def __len__(self):
        return len(self.dirs)


def pretty_seconds(seconds):
    """
    Converts a number in seconds to a string with the best time unit match.
    Ex:
    1 -> 1 second
    2 -> 2 seconds
    50 -> 50 seconds
    60 -> 1 minute
    3600 -> 1 hour
    7200 -> 2 hours
    """
    if seconds is None:
        return 'None'

    units = [
            (1, 'second'),
            (60, 'minute'),
            (60, 'hour'),
            (24, 'day'),
            (30, 'month'),
            (12, 'year'),
            ]

    value = seconds
    unit_index = 0
    # Finds the largest unit in which our value is not less than 1.
    while unit_index + 1 < len(units):
        multiplier, _ = units[unit_index + 1]
        if multiplier > value:
            break
        value /= multiplier
        unit_index += 1

    name = units[unit_index][1]
    rounded_value = round(value, 1)
    if rounded_value > 1:
        # We got lucky, appending an 's' works for all units so far.
        name += 's'

    return '{:g} {}'.format(rounded_value, name)

def profile():
    import cProfile
    cProfile.run('Workspace(r"E:\projects")')


if __name__ == '__main__':
    workspace = Workspace(r'E:\projects')
    for project in workspace:
        print(project.name, project.files.largest_file)
    #print(workspace['gl4'].repo.behind)
