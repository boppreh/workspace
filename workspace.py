from path import path

class Projects(object):
    def __init__(self):
        self.root = path(r'E:\projects')
        self.dirs = {d.basename(): d for d in self.root.dirs()
                     if (d / '.git').exists()}

    def __getitem__(self, name):
        return self.dirs[name]

if __name__ == '__main__':
    p = Projects()
    print(p['quine'])
