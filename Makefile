PREFIX ?= /usr
BINDIR = $(DESTDIR)$(PREFIX)/bin
LIBDIR = $(DESTDIR)$(PREFIX)/lib/edgecall
SHAREDIR = $(DESTDIR)$(PREFIX)/share/edgecall
DOCDIR = $(DESTDIR)$(PREFIX)/share/doc/edgecall

.PHONY: all install uninstall lint test check deb clean

all:
	@echo "Targets:"
	@echo "  make install     system-wide install (used by the deb postinst)"
	@echo "  make uninstall   remove system-wide install"
	@echo "  make deb         build the .deb package"
	@echo "  make lint        shellcheck + python -m py_compile"
	@echo "  make test        run the test suite"
	@echo "  make check       lint + test"

install:
	install -d $(BINDIR) $(LIBDIR)/edgecall $(SHAREDIR)/functions $(DOCDIR)
	install -m 0755 bin/edgecall            $(BINDIR)/edgecall
	install -m 0644 lib/edgecall/*.py       $(LIBDIR)/edgecall/
	install -m 0644 functions/*.py          $(SHAREDIR)/functions/
	install -m 0644 functions/motd.txt      $(SHAREDIR)/functions/motd.txt
	install -m 0644 functions/README.md     $(SHAREDIR)/functions/README.md
	install -m 0644 README.md               $(DOCDIR)/README.md
	install -m 0644 LICENSE                 $(DOCDIR)/LICENSE

uninstall:
	rm -f $(BINDIR)/edgecall
	rm -rf $(LIBDIR)
	rm -rf $(SHAREDIR)
	rm -rf $(DOCDIR)

lint:
	shellcheck scripts/*.sh || true
	python3 -m py_compile bin/edgecall lib/edgecall/*.py functions/*.py

test:
	PYTHONPATH=lib python3 -m pytest tests/ -q

check: lint test

deb:
	bash scripts/build-deb.sh

clean:
	rm -rf dist build *.deb
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
