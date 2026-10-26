"""Generate an UNAPPLIED generic renderer patch from pinned Git object copies.
Changes only .qa/host-patched and the reviewable patch file in this extension.
"""
from pathlib import Path
import shutil,difflib
ROOT=Path(__file__).resolve().parents[1];PIN=ROOT/'.qa/pinned/host';OUT=ROOT/'.qa/host-patched'
paths=['src/renderer/src/raycast-api/list-runtime.tsx','src/renderer/src/raycast-api/index.tsx','src/renderer/ExtensionRuntimeView.tsx','src/shared/extensionRuntime.ts']
shutil.copytree(PIN,OUT,dirs_exist_ok=True)
patch=[]
def replace(s,a,b,count=1):
 assert s.count(a)>=count,repr(a)
 return s.replace(a,b,count)
for p in paths:
 original=(PIN/p).read_text();s=original
 if p.endswith('/list-runtime.tsx'):
  s=replace(s,'type ListAccessory = {','type ListAccessory = {\n  value?: string')
  s=replace(s,'    actionId: typeof node.props?.actionId',"    value: typeof node.props?.value === 'string' ? node.props.value : undefined,\n    actionId: typeof node.props?.actionId")
  s=replace(s,'  onSearchTextChanged,\n  onLoadMore,','  onSearchTextChanged,\n  onDraftChanged,\n  onLoadMore,')
  s=replace(s,'  onSearchTextChanged: (searchText: string) => Promise<void> | void','  onSearchTextChanged: (searchText: string, draft?: Record<string, unknown>) => Promise<void> | void\n  onDraftChanged?: (draft: Record<string, unknown>) => void')
  s=replace(s,"    searchAccessory?.options[0]?.value ?? '',","    searchAccessory?.value ?? searchAccessory?.options[0]?.value ?? '',")
  s=replace(s,"  const lastSentQuery = useRef('')",'''  const draftRef = useRef<Record<string, unknown>>({ ...(root.props?.inputDraft as Record<string, unknown> | undefined) })
  const [draftTick, setDraftTick] = useState(0)
  const editDraft = (fields: Record<string, unknown>): Record<string, unknown> | undefined => {
    if (!root.props?.inputDraft) return undefined
    const draft = { ...draftRef.current, ...fields, revision: Number(draftRef.current.revision ?? 0) + 1 }
    draftRef.current = draft
    onDraftChanged?.(draft) // Ownership advances synchronously, before debounce/validation.
    setDraftTick((value) => value + 1)
    return draft
  }
  const lastSentQuery = useRef(typeof root.props?.searchText === 'string' ? root.props.searchText : '')
  const lastSentRevision = useRef(Number(draftRef.current.revision ?? 0))''')
  s=replace(s,"    if (typeof root.props?.searchText === 'string') {\n      setQuery(root.props.searchText)",'''    const incoming = root.props?.inputDraft as Record<string, unknown> | undefined
    if (incoming && Number(incoming.revision) < Number(draftRef.current.revision)) return
    if (incoming) draftRef.current = { ...incoming }
    if (typeof root.props?.searchText === 'string') {
      setQuery(root.props.searchText)''')
  s=replace(s,'  }, [root.props?.searchText])','  }, [root.props?.searchText, root.props?.inputDraft])')
  s=replace(s,"      if (!searchAccessory || searchAccessory.options.length === 0) return ''",'''      const incoming = root.props?.inputDraft as Record<string, unknown> | undefined
      if (incoming && Number(incoming.revision) < Number(draftRef.current.revision)) return current
      if (searchAccessory?.value !== undefined) return searchAccessory.value
      if (!searchAccessory || searchAccessory.options.length === 0) return '' ''')
  s=replace(s,'  }, [searchAccessory])','  }, [searchAccessory, root.props?.inputDraft])')
  s=replace(s,'    if (query === lastSentQuery.current) return',"    if (query === lastSentQuery.current && (!root.props?.inputDraft || Number(draftRef.current.revision) === lastSentRevision.current)) return")
  s=replace(s,'      void onSearchTextChanged(query)',"      lastSentRevision.current = Number(draftRef.current.revision ?? 0)\n      void onSearchTextChanged(query, root.props?.inputDraft ? { ...draftRef.current } : undefined)")
  s=replace(s,'  }, [query, onSearchTextChanged])','  }, [query, onSearchTextChanged, draftTick, root.props?.inputDraft])')
  s=replace(s,'                  setQuery(event.target.value)','                  editDraft({ searchText: event.target.value })\n                  setQuery(event.target.value)')
  s=replace(s,'                        setAccessoryValue(option.value)','                        const draft = editDraft({ searchText: query, filter: option.value })\n                        setAccessoryValue(option.value)')
  s=replace(s,'onRunPrimaryAction(searchAccessory.actionId, { value: option.value })','onRunPrimaryAction(searchAccessory.actionId, { value: option.value, ...(draft ? { __draft: draft } : {}) })')
  s=replace(s,": hasQuery\n      ? 'No matching applications'",": emptyView?.title || (hasQuery\n      ? 'No matching applications'")
  s=replace(s,": emptyView?.title || 'No list items'",": 'No list items')")
  s=replace(s,": hasQuery\n      ? 'Try a different app name or keyword.'",": emptyView?.description || (hasQuery\n      ? 'Try a different app name or keyword.'")
  s=replace(s,": emptyView?.description || ''",": '')")
 elif p.endswith('/index.tsx'):
  s=replace(s,'  onSearchTextChanged: (searchText: string) => Promise<void> | void','  onSearchTextChanged: (searchText: string, draft?: Record<string, unknown>) => Promise<void> | void\n  onDraftChanged?: (draft: Record<string, unknown>) => void')
  s=replace(s,'    onSearchTextChanged,\n    onLoadMore,','    onSearchTextChanged,\n    onDraftChanged,\n    onLoadMore,')
  s=replace(s,'              onLoadMore={onLoadMore}','              onLoadMore={onLoadMore}\n              onDraftChanged={onDraftChanged}')
 elif p.endswith('/ExtensionRuntimeView.tsx'):
  s=replace(s,'  const searchRequestSeq = useRef(0)','''  const searchRequestSeq = useRef(0)
  const inputDraft = useRef<Record<string, unknown> | undefined>(undefined)
  const handleDraftChanged = useCallback((draft: Record<string, unknown>): void => {
    inputDraft.current = { ...draft }
    searchRequestSeq.current += 1
  }, [])''')
  s=replace(s,'    setState(fromRunResult(initial))','    inputDraft.current = undefined\n    setState(fromRunResult(initial))')
  s=replace(s,'          const result = await window.tezbar.extensionRefreshSession','          const requestSeq = searchRequestSeq.current\n          const result = await window.tezbar.extensionRefreshSession')
  s=replace(s,"          if (cancelled || (result.ok && result.mode === 'unchanged')) return", "          if (cancelled || requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner || (result.ok && result.mode === 'unchanged')) return")
  s=replace(s,'      } catch (error) {\n          if (!cancelled)', '      } catch (error) {\n          if (!cancelled)') if False else s
  s=replace(s,'    async (searchText: string) => {','    async (searchText: string, draft?: Record<string, unknown>) => {')
  s=replace(s,'        searchText,\n      })','        searchText,\n        ...(draft ? { __draft: draft } : {}),\n      })')
  s=replace(s,'      if (!result.ok) {\n        console.error',"      if (result.ok && result.mode === 'view' && (result.sessionId !== state.sessionId || result.generation !== state.generation)) return\n      if (!result.ok) {\n        console.error")
  s=replace(s,'  const handleLoadMore = useCallback(async () => {','  const handleLoadMore = useCallback(async () => {\n    const requestSeq = searchRequestSeq.current')
  s=replace(s,'    if (currentSession.current !== sessionOwner) return','    if (currentSession.current !== sessionOwner || requestSeq !== searchRequestSeq.current) return')
  s=replace(s,'          <ExtensionRuntimeSurface', '          <ExtensionRuntimeSurface key={sessionOwner}')
  s=replace(s,'            onSearchTextChanged={handleSearchTextChanged}','            onSearchTextChanged={handleSearchTextChanged}\n            onDraftChanged={handleDraftChanged}')
  s=replace(s,'              setError(null)\n              const invokedAction','              const requestSeq = searchRequestSeq.current\n              setError(null)\n              const invokedAction')
  s=replace(s,'                formValues,\n              })','                formValues: state.root.props?.inputDraft ? { ...formValues, __draft: inputDraft.current ?? state.root.props.inputDraft } : formValues,\n              })')
  s=replace(s,'              if (currentSession.current !== sessionOwner) return','              if (currentSession.current !== sessionOwner || requestSeq !== searchRequestSeq.current) return')
  s=replace(s,'              const effectNoticeValue = effectNotice',"              if (result.mode === 'view' && (result.sessionId !== state.sessionId || result.generation !== state.generation)) return\n              const effectNoticeValue = effectNotice")
  s=replace(s,'      if (!result.ok) {\n        console.error', "      if (result.ok && result.mode === 'unchanged') return\n      if (!result.ok) {\n        console.error")
  s=replace(s,'              if (!result.ok) {', "              if (result.ok && result.mode === 'unchanged') return\n              if (!result.ok) {")
 elif p.endswith('/extensionRuntime.ts'):
  for result_type in ['ExtensionInvokeActionResult', 'ExtensionSearchTextChangedResult']:
   s=replace(s,'export type '+result_type+" =\n",'export type '+result_type+" =\n  | { ok: true; mode: 'unchanged' }\n")
  s=replace(s,'export type ExtensionSearchTextChangedRequest = {\n  sessionId: string','export type ExtensionSearchTextChangedRequest = {\n  /** Optional complete input snapshot for opt-in native views. */\n  __draft?: Record<string, unknown>\n  sessionId: string')
 out=OUT/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s)
 patch.extend(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='a/'+p,tofile='b/'+p))
(ROOT/'host-prerequisites/input-ownership.patch').write_text(''.join(patch))
print('Generated unapplied generic patch:',len(patch),'lines against ea100cee3f69711de12485ba061950c5fc65258f')
