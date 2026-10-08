# paper.html -> DOCX + PDF with EMBEDDED images (Word COM, no installs)
$ErrorActionPreference = 'Stop'
$base = "C:\Users\ASUS\Desktop\Network telementry\paper"
# image files in document order (must match paper.html) + target width in points (px * 0.75)
$imgs = @(
  @{ f = "figure1_testbed_architecture.png"; w = 465 },
  @{ f = "int_diagram.png"; w = 360 },
  @{ f = "dashboard.png";    w = 450 },
  @{ f = "fig2.png";         w = 465 },
  @{ f = "fig3.png";         w = 465 }
)
Add-Type -AssemblyName System.Drawing
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Open("$base\paper.html")
$sel = $word.Selection
$sel.SetRange(0, 0)
"images found: $($doc.InlineShapes.Count)"
for ($i = $doc.InlineShapes.Count; $i -ge 1; $i--) {
  $spec = $imgs[$i - 1]
  $old = $doc.InlineShapes.Item($i)
  $old.Range.Select()
  $sel.Delete() | Out-Null
  $pic = $sel.InlineShapes.AddPicture("$base\figs\$($spec.f)", $false)
  $gi = [System.Drawing.Image]::FromFile("$base\figs\$($spec.f)")
  $pic.LockAspectRatio = 0
  $pic.Width = $spec.w
  $pic.Height = $spec.w * $gi.Height / $gi.Width
  $gi.Dispose()
  "  [$i] $($spec.f) embedded, $($spec.w)x$([math]::Round($pic.Height,1))pt"
}
$doc.SaveAs2("$base\Network_Telemetry_Research_Paper.docx", 16)
$doc.SaveAs2("$base\Network_Telemetry_Research_Paper.pdf", 17)
$pages = $doc.ComputeStatistics(2)
$words = $doc.ComputeStatistics(0)
$doc.Close($false)
$word.Quit()
"RESULT pages=$pages words=$words"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$z = [System.IO.Compression.ZipFile]::OpenRead("$base\Network_Telemetry_Research_Paper.docx")
$media = $z.Entries | Where-Object { $_.FullName -like '*media*' }
"media entries in docx: $($media.Count)"
$media | ForEach-Object { "  $($_.FullName) $($_.Length) bytes" }
$z.Dispose()
