# Функция для определения кодировки файла по первым байтам (BOM). Если BOM не найден — считаем, что windows-1251.
function Get-FileEncoding {
  param([string]$Path)
  $fs = [System.IO.File]::Open($Path, 'Open', 'Read') # Открываем файл для чтения
  $bytes = New-Object byte[] 4                        # Буфер на 4 байта
  $fs.Read($bytes, 0, 4) | Out-Null                   # Читаем эти 4 байта
  $fs.Close()
  # Анализируем сигнатуру BOM и возвращаем понятное PowerShell имя кодировки
  switch -regex ($bytes -join ',') {
    '^239,187,191' { return "utf-8" }
    '^255,254,0,0' { return "utf-32" }
    '^255,254' { return "utf-16" }
    '^254,255' { return "big-endian-unicode" }
    default { return "windows-1251" }
  }
}

# --- В вашем примере теперь без автоматического GUID домена ---
$adGuid = Read-Host "Введите GUID домена (adGuid)"

foreach ($csv in (Get-ChildItem -Path $PWD -Filter '*.csv' | Where-Object { $_.Name -ne 'Sample.csv' })) {
  # 1. Определяем кодировку исходного файла, читаем весь файл как текст, пересохраняем во временный файл в windows-1251
  $origEncoding = Get-FileEncoding $csv.FullName
  $origText = [System.IO.File]::ReadAllText($csv.FullName, [System.Text.Encoding]::GetEncoding($origEncoding))
  $tempCsv = [System.IO.Path]::GetTempFileName()
  [System.IO.File]::WriteAllText($tempCsv, $origText, [System.Text.Encoding]::GetEncoding("windows-1251"))

  # 2. Работаем далее с временным файлом гарантированно в нужной кодировке
  $reader = New-Object System.IO.StreamReader($tempCsv, [System.Text.Encoding]::GetEncoding("windows-1251"))
  $firstLine = $reader.ReadLine()
  $reader.Close()

  # Определяем разделитель CSV (точка с запятой или запятая)
  if ($firstLine -match ";") { $delimiter = ";" }
  elseif ($firstLine -match ",") { $delimiter = "," }
  else { $delimiter = ";" }

  # Читаем временный файл как текст и парсим его в объект
  $bytes = [System.IO.File]::ReadAllBytes($tempCsv)
  $text = [System.Text.Encoding]::GetEncoding("windows-1251").GetString($bytes)
  $csvData = $text | ConvertFrom-Csv -Delimiter $delimiter

  # --- Заготовки для будущих XML ---
  $sysConfigXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<md:FullModel rdf:about="#_sysconfig">
<md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
<md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
<me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
</md:FullModel>
"@

  $energyXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<md:FullModel rdf:about="#_energy">
<md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
<md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
<me:Model.name>CIM16</me:Model.name>
</md:FullModel>
"@

  $updatedRows = @()
  foreach ($line in $csvData) {
    # Динамический поиск ключа name (надёжно, даже если был BOM)
    $nameKey = $line.PSObject.Properties.Name | Where-Object { $_ -match "name$" }
    $name = $line.$nameKey
    if ([string]::IsNullOrWhiteSpace($name)) { continue } # Пропуск пустых строк

    $login = $line.login
    $email = $line.email
    $mobilePhone = $line.mobilePhone
    $person_guid = $line.person_guid
    if ([string]::IsNullOrWhiteSpace($person_guid)) {
      $person_guid = [guid]::NewGuid().ToString()
    }
    $parent_sysconfig = $line.parent_sysconfig
    $parent_energy = $line.parent_energy

    # Для XML energy — раздельно ФИО
    $fio = $name -split ' '
    $fio_last = if ($fio.Length -ge 1) { $fio[0] } else { "" }
    $fio_first = if ($fio.Length -ge 2) { $fio[1] } else { "" }
    $fio_middle = if ($fio.Length -ge 3) { $fio[2] } else { "" }

    # XML sysconfig блок
    $sysConfigXml += @"
<cim:User rdf:about="#_$person_guid">
<cim:Principal.isEnabled>true</cim:Principal.isEnabled>
<cim:Principal.Domain rdf:resource="#_$adGuid" />
<cim:User.login>$login</cim:User.login>
<cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
<cim:IdentifiedObject.ParentObject rdf:resource="#_$parent_sysconfig" />
</cim:User>
"@

    # Блок email для energy.xml если есть e-mail
    $emailBlock = ""
    if ($email) {
      $emailBlock = @"
<cim:Person.electronicAddress>
  <cim:ElectronicAddress>
    <cim:ElectronicAddress.email1>$email</cim:ElectronicAddress.email1>
  </cim:ElectronicAddress>
</cim:Person.electronicAddress>
"@
    }
    # Блок мобильного телефона для energy.xml если есть телефон
    $phoneBlock = ""
    if ($mobilePhone) {
      $phoneBlock = @"
<cim:Person.mobilePhone>
  <cim:TelephoneNumber>
    <cim:TelephoneNumber.localNumber>$mobilePhone</cim:TelephoneNumber.localNumber>
  </cim:TelephoneNumber>
</cim:Person.mobilePhone>
"@
    }
    # XML energy блок
    $energyXml += @"
<cim:Person rdf:about="#_$person_guid">
<cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
<me:IdentifiedObject.ParentObject rdf:resource="#_$parent_energy" />
$emailBlock
<cim:Person.firstName>$fio_first</cim:Person.firstName>
<cim:Person.lastName>$fio_last</cim:Person.lastName>
<cim:Person.mName>$fio_middle</cim:Person.mName>
$phoneBlock
</cim:Person>
"@

    # Обновляем строку для итогового CSV
    $updatedRow = [PSCustomObject]@{
      name             = $name
      login            = $login
      email            = $email
      mobilePhone      = $mobilePhone
      person_guid      = $person_guid
      parent_energy    = $parent_energy
      parent_sysconfig = $parent_sysconfig
    }
    $updatedRows += $updatedRow
  }

  # Финализируем XML-файлы
  $sysConfigXml += @"
</rdf:RDF>
"@
  $energyXml += @"
</rdf:RDF>
"@

  # Записываем XML как utf-8 (всегда стандарт для интеграций)
  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'sysconfig.xml'), $sysConfigXml, [System.Text.Encoding]::UTF8)
  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'energy.xml'), $energyXml, [System.Text.Encoding]::UTF8)

  # Финальный CSV перезаписываем (в WIN-1251, это -Encoding Default)
  $updatedRows | Export-Csv -Path $csv.FullName -Delimiter $delimiter -Encoding Default -NoTypeInformation

  # Удаляем временный файл
  Remove-Item $tempCsv -ErrorAction SilentlyContinue
}

Write-Host "Обработка завершена. Все person_guid записаны в исходные CSV!"
