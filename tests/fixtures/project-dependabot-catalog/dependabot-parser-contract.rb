#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "fileutils"
require "json"
require "open3"
require "pathname"
require "toml-rb"

require "dependabot/dependency_file"
require "dependabot/source"
require "dependabot/gradle/file_parser"

def abort_contract(message)
  warn "Dependabot Gradle parser contract failed: #{message}"
  exit 1
end

def canonical(value)
  case value
  when Hash
    value.keys.map(&:to_s).sort.to_h do |key|
      original_key = value.keys.find { |candidate| candidate.to_s == key }
      [key, canonical(value.fetch(original_key))]
    end
  when Array
    value.map { |item| canonical(item) }
  else
    value
  end
end

def real_file(path, label)
  candidate = Pathname(path).expand_path
  resolved = candidate.realpath
  abort_contract("#{label} path must be canonical and non-symlinked") unless candidate == resolved
  abort_contract("#{label} must be a regular file") unless candidate.lstat.file?
  resolved
rescue Errno::ENOENT, Errno::ELOOP
  abort_contract("#{label} is missing or contains a symlink loop")
end

def git_head(root)
  output, status = Open3.capture2("git", "-C", root.to_s, "rev-parse", "HEAD")
  abort_contract("cannot read Dependabot core HEAD") unless status.success?
  output.strip
end

core_root_input = Pathname(ENV.fetch("DEPENDABOT_CORE_ROOT")).expand_path
core_root = core_root_input.realpath
abort_contract("Dependabot core path must be canonical") unless core_root_input == core_root
mapping_path = real_file(ENV.fetch("MAPPING_PATH"), "projection mapping")
catalog_path = real_file(ENV.fetch("GENERATED_CATALOG_PATH"), "generated catalog")
output_path = Pathname(ENV.fetch("OUTPUT_PATH")).expand_path
mapping = TomlRB.parse(mapping_path.read)
expected_commit = mapping.fetch("dependabot_core_commit")
actual_commit = git_head(core_root)
abort_contract("Dependabot core HEAD differs from the pinned commit") unless actual_commit == expected_commit

projection = mapping.fetch("projection")
catalog = TomlRB.parse(catalog_path.read)
catalog_libraries = catalog.fetch("libraries")
catalog_versions = catalog.fetch("versions")
catalog_file = Dependabot::DependencyFile.new(
  name: "gradle/libs.versions.toml",
  content: catalog_path.read
)
source = Dependabot::Source.new(
  provider: "github",
  repo: "bluetape4k/bluetape4k-projects",
  directory: "/"
)
dependencies = Dependabot::Gradle::FileParser.new(
  dependency_files: [catalog_file],
  source: source
).parse

dependencies_by_module = {}
dependencies.each do |dependency|
  abort_contract("parser returned duplicate module #{dependency.name}") if dependencies_by_module.key?(dependency.name)
  dependencies_by_module[dependency.name] = dependency
end
abort_contract("parser did not return exactly the ten projected dependencies") unless dependencies_by_module.length == projection.length

observed = projection.map do |entry|
  alias_name = entry.fetch("alias")
  module_name = entry.fetch("module")
  version_ref = entry.fetch("version_key")
  alias_entry = catalog_libraries.fetch(alias_name)
  abort_contract("generated alias #{alias_name} has the wrong module") unless alias_entry.fetch("module") == module_name
  abort_contract("generated alias #{alias_name} does not use the mapped version.ref") unless alias_entry.fetch("version").fetch("ref") == version_ref

  dependency = dependencies_by_module.delete(module_name)
  abort_contract("parser did not return #{module_name}") unless dependency
  requirement = dependency.requirements.find do |item|
    item[:file] == "gradle/libs.versions.toml" &&
      item.dig(:metadata, :property_name) == version_ref
  end
  abort_contract("parser did not report version.ref #{version_ref} for #{module_name}") unless requirement

  actual_version = dependency.version.to_s
  expected_version = catalog_versions.fetch(version_ref).to_s
  abort_contract("parser version differs from catalog for #{module_name}") unless actual_version == expected_version

  {
    "alias" => alias_name,
    "module" => module_name,
    "version_ref" => version_ref,
    "version" => actual_version
  }
end
abort_contract("parser returned unmapped dependencies") unless dependencies_by_module.empty?

fixture_path = Pathname(__FILE__).realpath
receipt = {
  "schema_version" => 1,
  "dependabot_core_commit" => actual_commit,
  "parser_fixture" => {
    "path" => fixture_path.to_s,
    "sha256" => Digest::SHA256.file(fixture_path).hexdigest
  },
  "generated_catalog" => {
    "path" => catalog_path.to_s,
    "sha256" => Digest::SHA256.file(catalog_path).hexdigest
  },
  "dependencies" => observed
}

FileUtils.mkdir_p(output_path.dirname)
File.write(output_path, JSON.generate(canonical(receipt)) + "\n")
puts "Dependabot Gradle parser contract PASS: #{observed.length} dependencies at #{actual_commit}"
