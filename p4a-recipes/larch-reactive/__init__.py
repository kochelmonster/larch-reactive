from pythonforandroid.recipe import CythonRecipe


class ReactiveRecipe(CythonRecipe):
    version = '4.0.8'
    url = ('http://localhost:9000/larch-reactive/'
           'larch-reactive-{version}.tar.gz')
    depends = ["setuptools"]
    need_stl_shared = True


recipe = ReactiveRecipe()
