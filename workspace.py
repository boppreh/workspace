from path import path

class Project(object):
    def __init__(self, path_):
        self.path = path_
        self.name = path_.basename()

    def __repr__(self):
        return '{} ({})'.format(self.name, self.path)

class Projects(object):
    def __init__(self):
        self.root = path(r'E:\projects')
        self.dirs = {}
        for d in self.root.dirs():
            if (d / '.git').exists():
                project = Project(d)
                self.dirs[project.name] = project

    def __getitem__(self, name):
        return self.dirs[name]

if __name__ == '__main__':
    p = Projects()
    print(p['quine'])
