import subprocess


def _esc(s: str) -> str:
    """Échappe une chaîne pour l'insertion dans un littéral AppleScript entre guillemets doubles."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def create_apple_note(title: str, body: str, folder: str = "Notes") -> str:
    t, b, f = _esc(title), _esc(body), _esc(folder)
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "{f}") then
                make new folder with properties {{name:"{f}"}}
            end if
            make new note at folder "{f}" with properties {{name:"{t}", body:"{t}\\n\\n{b}"}}
        end tell
    end tell
    '''
    _run_applescript(script)
    return f"Note '{title}' créée dans Apple Notes (dossier : {folder})."


def list_apple_notes(folder: str = "Notes", max_results: int = 10) -> list:
    f = _esc(folder)
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            set noteList to {{}}
            set allNotes to notes of folder "{f}"
            set counter to 0
            repeat with n in allNotes
                if counter >= {max_results} then exit repeat
                set end of noteList to (name of n & " | " & (modification date of n as string))
                set counter to counter + 1
            end repeat
            return noteList
        end tell
    end tell
    '''
    output = _run_applescript(script)
    if not output:
        return []
    return [line.strip() for line in output.split(",") if line.strip()]


def search_apple_notes(query: str) -> list:
    q_esc = _esc(query)
    script = f'''
    tell application "Notes"
        set results to {{}}
        set q to "{q_esc}"
        repeat with n in notes
            if (name of n contains q) or (body of n contains q) then
                set end of results to (name of n)
            end if
        end repeat
        return results
    end tell
    '''
    output = _run_applescript(script)
    if not output:
        return []
    return [line.strip() for line in output.split(",") if line.strip()]
