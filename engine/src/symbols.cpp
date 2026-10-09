#include "itb/symbols.hpp"

#include <deque>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace itb {
namespace {

struct Table {
  std::deque<std::string> names{""};  // deque keeps string_views stable
  std::unordered_map<std::string_view, Symbol> ids;
};

Table& table() {
  static Table t;
  return t;
}

}  // namespace

Symbol intern(std::string_view name) {
  if (name.empty()) return kNoSymbol;
  Table& t = table();
  if (auto it = t.ids.find(name); it != t.ids.end()) return it->second;
  if (t.names.size() > 0xFFFF) throw std::length_error("symbol table full");
  const auto id = static_cast<Symbol>(t.names.size());
  t.names.emplace_back(name);
  t.ids.emplace(t.names.back(), id);
  return id;
}

Symbol find_symbol(std::string_view name) {
  const Table& t = table();
  auto it = t.ids.find(name);
  return it == t.ids.end() ? kNoSymbol : it->second;
}

std::string_view symbol_name(Symbol s) {
  const Table& t = table();
  return s < t.names.size() ? std::string_view(t.names[s]) : std::string_view();
}

}  // namespace itb
