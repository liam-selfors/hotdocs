# Homebrew formula for the personal tap (D358), the repository
# liam-selfors/homebrew-hotdocs, installed with
#
#   brew install liam-selfors/hotdocs/hotdocs
#
# This is the tap's formula as a template; change both together. The tap's
# copy holds each release's real `url` and `sha256`. They stay out of this
# repository because the full secret scan reads long hex strings as secrets.
#
# It installs the downloaded sdist, whose checksum the formula pins, and its
# pinned dependencies from PyPI into a private virtual environment.
# Dependencies are installed from wheels, not built from source (DuckDB's
# source build is impractical), so this formula suits a personal tap, not
# homebrew-core. After each PyPI release, set the tap's `url` to the sdist
# URL that PyPI lists for it (https://pypi.org/pypi/hotdocs/<v>/json;
# `brew audit` rejects the short /packages/source/ form) and `sha256` to
# that file's (`shasum -a 256 hotdocs-<v>.tar.gz`).
class Hotdocs < Formula
  desc "Spec-driven agentic development: specs in, verified code out"
  homepage "https://github.com/liam-selfors/hotdocs"
  url "REPLACE_WITH_THE_SDIST_URL_PYPI_LISTS"
  sha256 "REPLACE_WITH_THE_RELEASED_SDIST_SHA256"
  license "Apache-2.0"

  depends_on "python@3.14"
  depends_on "node" => :recommended # only for components with javascript assets

  def install
    python = formula_opt_bin("python@3.14")/"python3.14"
    system python, "-m", "venv", libexec
    system libexec/"bin/pip", "install", "--no-cache-dir", buildpath
    bin.install_symlink libexec/"bin/hotdocs"
  end

  test do
    system "git", "init", "-q", "-b", "main"
    # --yes takes the first available provider; with none, init says so and
    # carries on, so the test needs no model provider.
    system bin/"hotdocs", "init", "--example", "--yes"
    assert_match "0 hard failure(s)", shell_output("#{bin}/hotdocs lint")
  end
end
