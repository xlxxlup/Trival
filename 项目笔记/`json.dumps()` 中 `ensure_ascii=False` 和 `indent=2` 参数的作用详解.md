# \`json.dumps()\` 中 \`ensure\_ascii=False\` 和 \`indent=2\` 参数的作用详解

好的，我们来详细解释一下 `json.dumps()` 中 `ensure_ascii=False` 和 `indent=2` 这两个参数的作用。

`json.dumps()` 是 Python 中 `json` 模块提供的一个函数，用于将 Python 对象（如字典、列表等）转换为 JSON 格式的字符串。

### 1. `ensure_ascii=False`

这个参数主要用于处理**非 ASCII 字符**，特别是中文、日文、韩文等 Unicode 字符。



* **默认行为 (**`ensure_ascii=True`**)**：


  * 当 `ensure_ascii` 为 `True`（默认值）时，`json.dumps()` 会将所有非 ASCII 字符（即 Unicode 码点大于 127 的字符）转换为 `\uXXXX` 形式的 Unicode 转义序列。

  * **示例**：



```
import json

data = {"name": "张三", "age": 25}

json\_str = json.dumps(data)  # 默认 ensure\_ascii=True

print(json\_str)
```

**输出**：



```
{"name": "\u5f20\u4e09", "age": 25}
```

这里的 `"张三"` 被转换成了 `"\u5f20\u4e09"`。这种形式的字符串是纯 ASCII 的，可以被任何 JSON 解析器正确解析，但对于人类阅读来说不够直观。



* **设置为&#x20;**`ensure_ascii=False`：


  * 当 `ensure_ascii` 为 `False` 时，`json.dumps()` 会**直接输出非 ASCII 字符**，而不会进行转义。

  * **示例**：



```
import json

data = {"name": "张三", "age": 25}

json\_str = json.dumps(data, ensure\_ascii=False)

print(json\_str)
```

**输出**：



```
{"name": "张三", "age": 25}
```

这里的 `"张三"` 被直接保留在 JSON 字符串中，非常易于阅读。

**什么时候使用&#x20;**`ensure_ascii=False`**？**



* 当你的 Python 对象中包含中文、日文等非英文字符，并且你希望生成的 JSON 字符串是人类可读的时。

* 当你确定接收 JSON 字符串的终端或应用程序能够正确处理 UTF-8 编码时。在现代 Web 开发和大多数应用中，这通常是默认情况。



***

### 2. `indent=2`

这个参数用于**美化 JSON 字符串的输出格式**，使其带有缩进，更易于阅读。



* **默认行为 (**`indent=None`**)**：


  * 当 `indent` 为 `None`（默认值）时，`json.dumps()` 会生成一个**紧凑的、没有多余空格和换行**的 JSON 字符串。

  * **示例**：



```
import json

data = {"name": "张三", "age": 25, "hobbies": \["读书", "运动"]}

json\_str = json.dumps(data, ensure\_ascii=False)  # 默认 indent=None

print(json\_str)
```

**输出**：



```
{"name": "张三", "age": 25, "hobbies": \["读书", "运动"]}
```

所有内容都在一行，对于复杂的、嵌套层次深的 JSON 数据，可读性很差。



* **设置为&#x20;**`indent=2`：


  * 当 `indent` 设为一个非负整数（如 `2`）时，`json.dumps()` 会使用该整数指定的空格数进行缩进，以美化输出。

  * **示例**：



```
import json

data = {"name": "张三", "age": 25, "hobbies": \["读书", "运动"]}

json\_str = json.dumps(data, ensure\_ascii=False, indent=2)

print(json\_str)
```

**输出**：



```
{

&#x20; "name": "张三",

&#x20; "age": 25,

&#x20; "hobbies": \[

&#x20;   "读书",

&#x20;   "运动"

&#x20; ]

}
```

JSON 字符串被格式化后，每个键值对占一行，并根据其嵌套深度进行缩进，结构非常清晰，易于阅读和调试。`indent=2` 表示每个层级缩进 2 个空格，你也可以根据喜好使用 `4` 等。

**什么时候使用&#x20;**`indent=2`**？**



* 在开发和调试阶段，为了方便查看生成的 JSON 数据结构。

* 当 JSON 数据需要被人工阅读和编辑时（例如，作为配置文件）。



***

### 总结



| 参数                   | 作用                                     | 示例效果             |
| -------------------- | -------------------------------------- | ---------------- |
| `ensure_ascii=False` | **禁用 ASCII 转义**，直接输出非 ASCII 字符（如中文）。   | `{"name": "张三"}` |
| `indent=2`           | **美化输出**，使用 2 个空格进行层级缩进，使 JSON 结构清晰可读。 | 格式化后的多行缩进结构      |

在你的代码中，`json.dumps(intervention_resp, ensure_ascii=False, indent=2)` 的作用就是：将 `intervention_resp` 这个 Python 对象转换成一个**包含中文且格式优美、易于阅读**的 JSON 字符串。这在打印日志或返回 API 响应时非常有用。

> （注：文档部分内容可能由 AI 生成）