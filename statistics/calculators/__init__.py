# -*- coding: utf-8 -*-

class BaseCalculator(object):

    def calculate(self, *args, **kwargs):
        raise NotImplementedError()
