try:
    import lxml
except ImportError:
    # if lxml extras is not installed, use h5 api
    from .h5 import FeedH5Api as FeedApi
else:
    # in v12 the default manner is web api
    from .web import FeedWebApi as FeedApi

    del lxml
