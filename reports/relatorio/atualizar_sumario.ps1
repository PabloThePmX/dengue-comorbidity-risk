# Passo opcional após gerar_docx.js: abre o .docx no Word (invisível), atualiza o sumário (campo TOC)
# e regrava o arquivo, para o sumário já vir preenchido. Uso:
#   powershell -File atualizar_sumario.ps1 -Docx <entrada.docx> -Out <saida.docx>
# (o gerador já marca o documento para atualizar campos ao abrir; este passo só pré-preenche)
param([string]$Docx, [string]$Out)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($Docx, $false, $false)
  $doc.Repaginate()
  foreach ($t in $doc.TablesOfContents) { $t.Update() }
  $doc.Fields.Update() | Out-Null
  foreach ($t in $doc.TablesOfContents) { $t.Update() }
  $doc.SaveAs2($Out, 16)
  $doc.Close($false)
  "SAVED"
} finally { $word.Quit() }
