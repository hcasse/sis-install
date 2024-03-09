CONFIG = ../config.py

TESTS = $(wildcard test-*.in)
GOALS = $(TESTS:.in=)

all: $(GOALS)

test-%: test-%.in
	@echo -n "Testing $* ... "
	@$(CONFIG) -i $< -o $(<:.in=.out) -q
	@if diff $(<:.in=.out) $(<:.in=.ref); then \
		echo "success!"; \
	else \
		echo "failed!"; \
	fi

run-%: test-%.in
	$(CONFIG) -i $< -o $(<:.in=.out) -q
