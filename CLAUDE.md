## Package management

This project manages Python dependencies and execution with `uv`.

Use `uv add <dependency>` to add a dependency.

Use `uv run <command>` to run a command.

Use `uv run pytest` to run tests.

Use `uv run ruff format` to format code.

Use `uv run ruff check` to check for lint errors; add `--fix` to fix.

## Comments

- Avoid descriptive comments that simply repeat what the code does.

  For example, here's a bad descriptive comment:

  ```
  # process all items
  for item in items:
      process(item)
  ```

- Comments may be used, sparingly, to explain why the code does something:

  For example, here's a comment which may be useful:

  ```
  for item in items:
      process(item or '') # item may be None, but process only handles strings
  ```

- Even explanatory comments may be excessive, keep them for rare and obscure cases.
- A good codebase may have no comments at all.

## Layout

- A function should ideally fit on the screen: 50 lines or less.
- A module should ideally be under 300 lines of code.
- Split long functions and modules to smaller functions and submodules.
- Splitting shouldn't be abused; sometimes the right length for a function or module is longer than these guidelines.
- `if` statements should implement the shorter branch.

  For example, this is bad:

  ```
  def process_item(item: Item) -> None:
      if is_ready_for_processing(item):
          # 20 processing lines
          return
      raise ValueError(f"{item} not ready")
  ```

  Prefer instead:

  ```
  def process_item(item) -> None:
      if not is_ready_for_processing(item):
          raise ValueError(f"{item} not ready")
      # 20 processing lines, implicit return
  ```

## Tests

### Avoid excessive mocking.

It's better to test real behaviour for many kinds of small/local side effects. For example, creating/changing small files, creating/killing processes, or local network connections should simply be tested locally by arranging and tearing down the relevant setup (files, processes, network endpoints, etc).

For large/distributed side effects, you may use mocks.

### Test your code

Do not test your dependencies. For example, using an external argument parsing library and testing that `--help` prints usage correctly or that `add_arg('-foo', type=int)` really validates `foo` is an `int` is excessive.

## Dependencies

Under `code/` you will find the code of some of your main dependencies. You are advised to read the docs or code of those dependencies when asked to use them; the docs and code there might be more recent than your training data, and you should seriously consider looking there rather than in your own memory or online.
