from osclib.comments import CommentAPI
from osclib.request_finder import RequestFinder


class IgnoreCommand(object):
    MESSAGE = 'Removed from active backlog.'
    COMMENT_TEMPLATE = '(Automated comment) Request marked as ignored, reason: "{}"'

    def __init__(self, api):
        self.api = api
        self.comment = CommentAPI(self.api.apiurl)

    def perform(self, requests, message=None):
        """
        Ignore a request from "list" and "adi" commands until unignored.
        """

        for request_id in RequestFinder.find_sr(requests, self.api):
            print('{}: ignored'.format(request_id))
            comment = message if message else self.MESSAGE
            self.api.add_ignored_request(request_id, comment)
            self.comment.add_comment(request_id=str(request_id), comment=self.COMMENT_TEMPLATE.format(comment))

        return True
