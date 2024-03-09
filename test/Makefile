CONFIG = ../config.py

test-include: test-include.in
	$(CONFIG) -i $< -o $(<:.in=.out)
	diff $(<:.in=.out) $(<:.in=.ref)

