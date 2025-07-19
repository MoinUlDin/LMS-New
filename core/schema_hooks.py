# def custom_preprocessing_hook(endpoints):
#     """
#     Remove problematic views from schema generation.
#     """
#     filtered = []
#     for (path, path_regex, method, callback) in endpoints:
#         view_class = getattr(callback, 'cls', None)
#         if view_class and view_class.__name__ in [
#             'DepartmentViewSet',
#             'SessionSettingsViewSet'
#         ]:
#             continue  # Exclude this view from schema
#         filtered.append((path, path_regex, method, callback))
#     return filtered
