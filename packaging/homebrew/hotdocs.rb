# Homebrew formula for the personal tap (D358), the repository
# liam-selfors/homebrew-hotdocs, installed with
#
#   brew install liam-selfors/hotdocs/hotdocs
#
# This is the tap's formula; change both together.
# It installs the downloaded sdist, whose checksum is pinned below, and its
# pinned dependencies from PyPI into a private virtual environment.
# Dependencies are installed from wheels, not built from source (DuckDB's
# source build is impractical), so this formula suits a personal tap, not
# homebrew-core. After each PyPI release, set `url` to the sdist URL that
# PyPI lists for it (https://pypi.org/pypi/hotdocs/<v>/json, `brew audit`
# rejects the short /packages/source/ form) and `sha256` to that file's
# (`shasum -a 256 hotdocs-<v>.tar.gz`).
class Hotdocs < Formula
  desc "Spec-driven agentic development: specs in, verified code out"
  homepage "https://github.com/liam-selfors/hotdocs"
  url "https://files.pythonhosted.org/packages/21/85/9c4b3d75d5ccc024f85d59deb542377efa3e152fb5d1a5b89837bde86913/hotdocs-0.1.0a1.tar.gz"
  sha256 "42f9ee2deeab2e64b8e622a0cfe108d83b81b88798c850e677e85f505ada5959"
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
