
import config

class One(config.Source):

	def __init__(self, args):
		config.Source.__init__(self)

	def eval(self, env):
		return "1"

config.Source.declare("!one", One)
