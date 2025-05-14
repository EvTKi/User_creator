# Функция для определения кодировки файла по сигнатуре BOM или по умолчанию считает windows-1251 (ANSI)
function Get-FileEncoding {
  param([string]$Path)
  $fs = [System.IO.File]::Open($Path, 'Open', 'Read')            # Открываем файл для чтения
  $bytes = New-Object byte[] 4                                   # Буфер на 4 байта
  $fs.Read($bytes, 0, 4) | Out-Null                             # Читаем первые 4 байта
  $fs.Close()                                                   # Закрываем файл

  # Определяем сигнатуру BOM и, соответственно, кодировку
  switch -regex ($bytes -join ',') {
    '^239,187,191' { return "utf-8" }               # UTF-8 с BOM
    '^255,254,0,0' { return "utf-32" }
    '^255,254' { return "utf-16" }              # UTF-16 Little-Endian
    '^254,255' { return "big-endian-unicode" }  # UTF-16 Big-Endian
    default { return "windows-1251" }        # если не совпало — считаем ANSI/CP1251
  }
}

# Запрос пользователю
$domainAnswer = Read-Host 'Требуется добавлять пользователей из домена? (Y/N)'
$domainAnswer = $domainAnswer.ToLower()

if ($domainAnswer -eq 'y' -or $domainAnswer -eq 'н') {
  # Положительный ответ – берем GUID домена из AD
  $adGuid = (Get-ADDomain).ObjectGUID.Guid
}
else {
  # Отрицательный ответ – запрашиваем вручную
  $adGuid = Read-Host "Введите GUID домена (adGuid)"
}


# Проходим по всем CSV-файлам в текущей папке
foreach ($csv in (Get-ChildItem -Path $PWD -Filter '*.csv')) {

  $encoding = Get-FileEncoding $csv.FullName        # Определяем кодировку файла

  # Получаем первую строку файла с определенной кодировкой для определения разделителя
  $reader = New-Object System.IO.StreamReader($csv.FullName, [System.Text.Encoding]::GetEncoding($encoding))
  $firstLine = $reader.ReadLine()
  $reader.Close()

  # Находим разделитель: если нашли ;, то это точка с запятой, если ,, то запятая, по умолчанию ;
  if ($firstLine -match ";") { $delimiter = ";" }
  elseif ($firstLine -match ",") { $delimiter = "," }
  else { $delimiter = ";" }

  # Читаем сразу весь файл как текст с определённой кодировкой
  $bytes = [System.IO.File]::ReadAllBytes($csv.FullName)
  $text = [System.Text.Encoding]::GetEncoding($encoding).GetString($bytes)

  # Преобразуем текст в объекты PowerShell по заголовкам таблицы (разделитель как определили)
  $csvData = $text | ConvertFrom-Csv -Delimiter $delimiter

  # Заготовка для XML-файла sysconfig
  $sysConfigXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<md:FullModel rdf:about="#_sysconfig">
  <md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
  <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
  <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
</md:FullModel>
"@

  # Заготовка для XML-файла energy
  $energyXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<md:FullModel rdf:about="#_energy">
  <md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
  <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
  <me:Model.name>CIM16</me:Model.name>
</md:FullModel>
"@

  $updatedRows = @() # Хранилище обновлённых строк для последующего экспорта

  # Разбор каждой строки CSV
  foreach ($line in $csvData) {
    $name = $line.name
    $login = $line.login
    $person_guid = $line.person_guid
    # Если GUID пустой — генерируем новый
    if ([string]::IsNullOrWhiteSpace($person_guid)) {
      $person_guid = [guid]::NewGuid().ToString()
    }
    $parent_sysconfig = $line.parent_sysconfig
    $parent_energy = $line.parent_energy

    # Разбиваем ФИО по пробелу для energy.xml
    $fio = $name -split ' '
    $fio_last = if ($fio.Length -ge 1) { $fio[0] } else { "" }
    $fio_first = if ($fio.Length -ge 2) { $fio[1] } else { "" }
    $fio_middle = if ($fio.Length -ge 3) { $fio[2] } else { "" }

    # Добавляем в sysConfigXml XML-блок для пользователя
    $sysConfigXml += @"
<cim:User rdf:about="#_$person_guid">
  <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
  <cim:Principal.Domain rdf:resource="#_$adGuid" />
  <cim:User.login>$login</cim:User.login>
  <cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
  <cim:IdentifiedObject.ParentObject rdf:resource="#_$parent_sysconfig" />
</cim:User>
"@

    # Добавляем в energyXml XML-блок для персоны
    $energyXml += @"
<cim:Person rdf:about="#_$person_guid">
  <cim:Person.firstName>$fio_first</cim:Person.firstName>
  <cim:Person.lastName>$fio_last</cim:Person.lastName>
  <cim:Person.mName>$fio_middle</cim:Person.mName>
  <cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
  <me:IdentifiedObject.ParentObject rdf:resource="#_$parent_energy" />
</cim:Person>
"@

    # Формируем обновлённый объект для экспорта обратно в CSV
    $updatedRow = [PSCustomObject]@{
      name             = $name
      login            = $login
      person_guid      = $person_guid
      parent_energy    = $parent_energy
      parent_sysconfig = $parent_sysconfig
    }
    $updatedRows += $updatedRow
  }

  # Завершаем XML-файлы
  $sysConfigXml += @"
</rdf:RDF>
"@
  $energyXml += @"
</rdf:RDF>
"@

  # Сохраняем XML-файлы как UTF-8 (с BOM)
  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'sysconfig.xml'), $sysConfigXml, [System.Text.Encoding]::UTF8)
  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'energy.xml'), $energyXml, [System.Text.Encoding]::UTF8)

  # Подбираем нужное имя кодировки для Export-Csv
  $exportEncoding = $encoding
  if ($exportEncoding -eq "utf-8") { $exportEncoding = "UTF8" }
  if ($exportEncoding -eq "utf-16") { $exportEncoding = "Unicode" }
  if ($exportEncoding -eq "utf-32") { $exportEncoding = "UTF32" }
  if ($exportEncoding -eq "big-endian-unicode") { $exportEncoding = "BigEndianUnicode" }
  if ($exportEncoding -eq "windows-1251") { $exportEncoding = "Default" }

  # Экспортируем новый CSV с тем же разделителем и исходной кодировкой
  $updatedRows | Export-Csv -Path $csv.FullName -Delimiter $delimiter -Encoding $exportEncoding -NoTypeInformation
}

Write-Host "Обработка завершена. Все person_guid записаны в исходные CSV!"
