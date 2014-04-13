from collections import Counter
from pathlib import Path
from time import clock

languages_by_extension = {'.pyw': 'Python',
                          '.py': 'Python',
                          '.go': 'Go',
                          '.nim': 'Nimrod',
                          '.js': 'Javascript',
                          '.html': 'Javascript',
                          '.as': 'ActionScript',
                          '.java': 'Java'}

class Project(object):
    def __init__(self, path):
        self.path = path
        self.name = path.name

        start = clock()
        self.refresh()
        end = clock()
        self.processing_time = int((end - start) * 100) / 100

    def refresh(self):
        gitignore = self.path / '.gitignore'
        self.ignored_patterns = []
        if gitignore.exists():
            with gitignore.open() as f:
                for line in f.read().split():
                    if not line.startswith('#'):
                        self.ignored_patterns.append(line)

        self.files = []
        self._refresh_files(self.path)

        languages = Counter(languages_by_extension[f.suffix] for f in self.files)
        self.language = languages.most_common()[0][0]
        self.file_count = len(self.files)

    def _refresh_files(self, path):
        if path.name.startswith('.'):
            return

        for pattern in self.ignored_patterns:
            if path.match(pattern):
                return

        if path.is_file():
            if path.suffix in languages_by_extension:
                self.files.append(path)
        else:
            for f in path.iterdir():
                self._refresh_files(f)

    def __repr__(self):
        return '{} ({})'.format(self.name, self.path)

class Projects(object):
    def __init__(self):
        self.root = Path(r'E:\projects')
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
    #p = Project(Path(r'E:\projects\activity'))
    #exit()
    projects = Projects()
    for project in projects:
        print(project, project.language, project.processing_time)
