import json
import mesop as me
import pandas as pd

from state.state import SessionTask, StateTask, ContentPart

def message_string(content: ContentPart) -> str:
  if isinstance(content, str):
    return content
  return json.dumps(content)

@me.component
def task_card(tasks: list[SessionTask]):
  """Task card component"""
  columns = ["Conversation ID", "Task ID", "Description", "Status", "Output"]
  df_data = dict([(c, []) for c in columns])
  for task in tasks:
    # Get session ID
    session_id = task.session_id

    # Get task ID
    task_id = task.task.task_id

    # Get description
    description = ""
    if hasattr(task.task.message, 'content') and task.task.message.content:
      if isinstance(task.task.message.content, list):
        description = '\n'.join(message_string(x[0]) for x in task.task.message.content)
      elif isinstance(task.task.message.content, dict):
        description = message_string(task.task.message.content)

    # Get status
    status = task.task.state if task.task.state else "unknown"

    # Get output
    output = flatten_artifacts(task.task)

    # Add to dataframe
    df_data["Conversation ID"].append(session_id)
    df_data["Task ID"].append(task_id)
    df_data["Description"].append(description)
    df_data["Status"].append(status)
    df_data["Output"].append(output)

  df = pd.DataFrame(
      pd.DataFrame(df_data),
      columns=columns)
  with me.box(
      style=me.Style(
          display="flex",
          justify_content="space-between",
      )
  ):
    me.table(
        df,
        header=me.TableHeader(sticky=True),
        columns=dict([(c, me.TableColumn(sticky=True)) for c in columns]),
    )

def flatten_artifacts(task: StateTask) -> str:
  parts = []

  # Handle case when artifacts is None or empty
  if not task.artifacts:
    return ""

  for a in task.artifacts:
    # Handle both list and dict formats for artifacts
    if isinstance(a, list):
      for p in a:
        if p[1] == 'text/plain' or p[1] == 'application/json':
          parts.append(message_string(p[0]))
        else:
          parts.append(p[1])
    elif isinstance(a, dict) and 'parts' in a:
      # Handle streaming format where artifact has 'parts' key
      for p in a['parts']:
        if isinstance(p, dict) and 'type' in p and 'text' in p:
          if p['type'] == 'text':
            parts.append(p['text'])
        else:
          parts.append(str(p))

  return '\n'.join(parts)

