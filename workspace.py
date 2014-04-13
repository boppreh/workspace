from pathlib import Path

class Project(object):
    def __init__(self, path):
        self.path = path
        self.name = path.name
        self.language = self._detect_language()

    def _detect_language(self):
        languages_by_extension = {'.pyw': 'Python',
                                  '.py': 'Python',
                                  '.go': 'Go',
                                  '.nim': 'Nimrod',
                                  '.js': 'Javascript',
                                  '.html': 'Javascript',
                                  '.as': 'ActionScript',
                                  '.java': 'Java'}

        for f in self.path.glob('**/*.*'):
            if f.suffix in languages_by_extension:
                return languages_by_extension[f.suffix]

        return 'Unknown'

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
    projects = Projects()
    for project in projects:
        print(project, project.language)
