<?php
/*
error_reporting(E_ALL);
ini_set('display_errors', 1);
*/
// Tennis-Webcam, Dateiformat: Immer webcam.jpg wird überschrieben bei neuer Aufnahme -> einstellbar in der Webcam.
$tennisordner = 'tennis'; // Ordner für die Tenniswebcambilder.
$tenniswebcam_letztesBild = $tennisordner.'/webcam.jpg'; // Aufnahme der Webcam.
$tenniswebcam_bildanzeige = $tennisordner.'/webcam_live.jpg'; // Ausgabe auf der Webseite.

// Da zuerst die leere Datei mit Dateiname webcam.jpg mit 0 kb per FTP übertragen wird, dann 2-4 s Upload-/Verarbeitungszeit der ca. 120 kb, dann der Kopier-/Nachbearbeitungsvorgang (ca. 60 kb), ergibt es zu oft Bildanzeige-/Webseitenfehler, wenn auf filesize nicht abgefragt werden würde. Falls keine neue Aufnahme (= Datei: webcam.jpg) vorhanden ist, muss nichts gemacht (aktualisieren/austauschen) werden. Die webcam.jpg wird nach Verarbeitung gelöscht und die Webcam erstellt diese Datei bei neuer Aufnahme erneut.

// Gibt es eine Aufnahme, die die Webcam übertragen hat? Ist die Datei lesbar und größer als 60 kb?
if( file_exists($tenniswebcam_letztesBild) and (is_readable($tenniswebcam_letztesBild)) and (filesize($tenniswebcam_letztesBild) > 60000) ){

	// Bild mit dessen Abmessung laden.
	$tenniswebcam_quelle = imagecreatefromjpeg($tenniswebcam_letztesBild); // Bild laden.
	list($tenniswebcam_breite, $tenniswebcam_hoehe) = getimagesize($tenniswebcam_letztesBild); // Abmessung des Bilds auslesen.

	// Maße definieren. 2560 x 1440 px (Original), 896 x 672 px (balanciert). Maximale Darstellung auf der Webseite: 550 x 309 px (550 x 413 px wäre ungeschnitten).
	$tenniswebcam_neueBreite = 896; // 896 ist Original
	$tenniswebcam_neueHoehe = 672; // 672 ist Original
	$tenniswebcam_neueBreite_geschnitten = 896;
	$tenniswebcam_neueHoehe_geschnitten = 504; // Kleinere Höhe (504 px) passend zu den Padelwebcams.

	// Neues leeres Bild mit kleineren Maßen erstellen.
	$tenniswebcam_verkleinert = imagecreatetruecolor($tenniswebcam_neueBreite, $tenniswebcam_neueHoehe);

	// Neues Bild mit kleineren Maßen auf das leere überschreiben.
	imagecopyresampled($tenniswebcam_verkleinert, $tenniswebcam_quelle, 0, 0, 0, 0, $tenniswebcam_neueBreite, $tenniswebcam_neueHoehe, $tenniswebcam_breite, $tenniswebcam_hoehe);

	// Unteren Teil des Bilds abschneiden, da es dort nichts Relevantes zu sehen gibt und dass die Maße zu den Padelwebcams passen.
	$tenniswebcam_verkleinert_geschnitten = imagecrop($tenniswebcam_verkleinert, ['x' => 0, 'y' => 0, 'width' => $tenniswebcam_neueBreite_geschnitten, 'height' => $tenniswebcam_neueHoehe_geschnitten]);

	// Verkleinertes Bild speichern.
	imagejpeg($tenniswebcam_verkleinert_geschnitten, $tenniswebcam_bildanzeige, 50);

	// Speicher freigeben.
	imagedestroy($tenniswebcam_quelle);
	imagedestroy($tenniswebcam_verkleinert);
	imagedestroy($tenniswebcam_verkleinert_geschnitten);

	// Lösche das übertragene originale Aufnahmebild der Webcam, welche nach dem Kopiervorgang zu Ausgabe nicht mehr benötigt wird.
	unlink($tennisordner.'/webcam.jpg');
}

// Padel-Webcams, Dateiformat: Padel_00_yyyymmddhhmmss und Padel_01_yyyymmddhhmmss
$padelordner = 'padel';

// Erst alle vorhandenen Webcamaufnahmen durchgehen und die aktuelle der jeweiligen der zwei Padelwebcams kopieren. Ordner werden automatisch von der Webcam nach Jahr, Monat, Tag erstellt und abgelegt. Ein Cronjob im Strato Hostingpaket löscht die Ordner täglich.

$jahr = date('Y'); // JJJJ
$monat = date('m'); // MM
$tag = date('d'); // TT

// Initialisiere die Arrays für die vorhandenen Bilder jeder Webcam.
$bilder_Padel_00 = array();
$bilder_Padel_01 = array();

// Existiert der Ordner des heutigen Tags?
if( is_dir($padelordner.'/'.$jahr.'/'.$monat.'/'.$tag) ){
	
	// Hole alle Dateien im heutigen Ordner. Absteigend sortiert, damit der aktuellste Zeitstempel im ersten Index steht.
	$bilder = scandir($padelordner.'/'.$jahr.'/'.$monat.'/'.$tag, SCANDIR_SORT_DESCENDING);
	
	// BUGFIX: Verzeichniseinträge '.' und '..' explizit ausschließen, bevor filesize() aufgerufen wird.
	// Bilderarray in zwei Arrays aufteilen, damit jede Webcam ein eigenes Array hat.
	foreach ($bilder as $bild){
		// Verzeichniseinträge überspringen.
		if($bild === '.' || $bild === '..') continue;

		$bildpfad = $padelordner.'/'.$jahr.'/'.$monat.'/'.$tag.'/'.$bild;

		// Ist die Datei größer als 100 kb? Weil zuerst der Dateiname mit 0 kb übertragen wird, dann 2-4 s Verarbeitungszeit, dann der Kopiervorgang die restlichen kb schnell überträgt.
		if( is_file($bildpfad) and (filesize($bildpfad) > 100000) ){
			$eineDerBeidenPadelwebcams = substr($bild, 0, 8); // Padel_00 oder Padel_01 holen, um die Bilder der beiden Webcams zu unterscheiden.

			// Die Aufnahme welcher Webcam ist es? Zwei Arrays je nach Webcam füllen.
			if($eineDerBeidenPadelwebcams == 'Padel_00'){ // Webcam 1
				array_push($bilder_Padel_00, $bild);
			}
			elseif($eineDerBeidenPadelwebcams == 'Padel_01'){ // Webcam 2
				array_push($bilder_Padel_01, $bild);
			}
		}
	}

	// BUGFIX: Sicherstellen, dass für beide Webcams mindestens ein Bild vorhanden ist, bevor darauf zugegriffen wird.
	if( !empty($bilder_Padel_00) and !empty($bilder_Padel_01) ){

		// Aufgrund absteigender Sortierung bei scandir (s.o.) ist das aktuellste Bild der erste Index, also [0]. Diese Bilder holen.
		$padelwebcam1_letztesBild = $padelordner.'/'.$jahr.'/'.$monat.'/'.$tag.'/'.$bilder_Padel_00[0];
		$padelwebcam2_letztesBild = $padelordner.'/'.$jahr.'/'.$monat.'/'.$tag.'/'.$bilder_Padel_01[0];

		// Zielordner und -datei festlegen.
		$padelwebcam1_bildanzeige = $padelordner.'/webcam1_live.jpg';
		$padelwebcam2_bildanzeige = $padelordner.'/webcam2_live.jpg';

		// Bild mit dessen Abmessung laden.
		$padelwebcam1_quelle = imagecreatefromjpeg($padelwebcam1_letztesBild); // Bild laden.
		list($padelwebcam1_breite, $padelwebcam1_hoehe) = getimagesize($padelwebcam1_letztesBild); // Abmessung des Bilds auslesen.
		$padelwebcam2_quelle = imagecreatefromjpeg($padelwebcam2_letztesBild); // Bild laden.
		list($padelwebcam2_breite, $padelwebcam2_hoehe) = getimagesize($padelwebcam2_letztesBild); // Abmessung des Bilds auslesen.

		// Maße: 2560 x 1440 px (Original). Maximale Darstellung auf der Webseite: 550 x 309 px.
		$padelwebcam1_neueBreite = 896;
		$padelwebcam1_neueHoehe = 504;
		$padelwebcam2_neueBreite = 896;
		$padelwebcam2_neueHoehe = 504;

		// Neues leeres Bild mit kleineren Maßen erstellen.
		$padelwebcam1_verkleinert = imagecreatetruecolor($padelwebcam1_neueBreite, $padelwebcam1_neueHoehe);
		$padelwebcam2_verkleinert = imagecreatetruecolor($padelwebcam2_neueBreite, $padelwebcam2_neueHoehe);

		// Neues Bild mit kleineren Maßen auf das leere überschreiben.
		imagecopyresampled($padelwebcam1_verkleinert, $padelwebcam1_quelle, 0, 0, 0, 0, $padelwebcam1_neueBreite, $padelwebcam1_neueHoehe, $padelwebcam1_breite, $padelwebcam1_hoehe);
		imagecopyresampled($padelwebcam2_verkleinert, $padelwebcam2_quelle, 0, 0, 0, 0, $padelwebcam2_neueBreite, $padelwebcam2_neueHoehe, $padelwebcam2_breite, $padelwebcam2_hoehe);

		// Verkleinertes Bild speichern.
		imagejpeg($padelwebcam1_verkleinert, $padelwebcam1_bildanzeige, 50);
		imagejpeg($padelwebcam2_verkleinert, $padelwebcam2_bildanzeige, 50);

		// Speicher freigeben.
		imagedestroy($padelwebcam1_quelle);
		imagedestroy($padelwebcam2_quelle);
		imagedestroy($padelwebcam1_verkleinert);
		imagedestroy($padelwebcam2_verkleinert);

		// Da nun die aktuellen Bilder kopiert sind, können alle Originaldateien gelöscht werden. Wird über einen Cronjob im Strato Hosting-Paket täglich gemacht.
	}	
}


echo'
<html>
	<head>
        <meta name="description" content="Webcams Tennis- & Padel-Club Grötzingen">
        <title>Webcams Tennis- & Padel-Club Grötzingen</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
		<meta name="keywords" content="Tennis, Padel, Club, Grötzingen, Webcam, Karlsruhe">
		<meta name="author" content="Nils Gräber">
		<meta http-equiv="refresh" content="30">		
		<link rel="icon" href="tpc_logo_75px.jpg">
        <link href="webcam.css" rel="stylesheet" type="text/css">
	</head>
	<body>		
		<div class="container">
			<div class="header-container">
				<a class="tpcg" href="https://www.tpc-groetzingen.de" alt="Tennis- & Padel-Club Grötzingen" title="Tennis- & Padel-Club Grötzingen" target="_blank"><img class="logo-tpcg" src="tpc_logo_75px.jpg"/></a>
				<div class="ueberschrift-container">
					<h1>TPCG-Live</h1>
					<h2>Webcams Tennis- & Padel-Club Grötzingen</h2>
				</div>
				<a class="lets-netz" href="https://www.tpcg-lets-netz.de" alt="Let\'s Netz" title="Let\'s Netz" target="_blank"><img class="logo-letsnetz" alt="Let\'s Netz" title="Let\'s Netz" src="letsnetz.jpg"/></a>
			</div>
			
			<div class="container-text">
				<div class="aktualisieren"><a href="https://www.tpcg-live.de" alt="TPCG Webcams" title="TPCG Webcams">Aktualisieren</a></div>
				<p>Den Club aus der Ferne erleben. Regelmäßige Bildaufnahme, außer nachts.</p>
			</div>

			<div class="webcam">
				<div class="webcamtennis">
					<h3>Tennis</h3>
					<img class="webcambildplatzhalter" alt="Webcam Eingangsbereich" title="Webcam Eingangsbereich" src="platzhalter.jpg"/>
					<img class="webcambildreal" alt="Webcam Eingangsbereich" title="Webcam Eingangsbereich" src="tennis/webcam_live.jpg"/>
					<p><i>Eingangsbereich der Anlage bei den Tennisplätzen 4+5.</i></p>
				</div>
				<div class="webcampadel">
					<div class="webcampadel1">
						<h3>Padel</h3>
						<img class="webcambildplatzhalter" src="platzhalter.jpg" alt="Webcam Lounge zum Padel Center Court" title="Webcam Lounge zum Padel Center Court"/>
						<img class="webcambildreal" src="padel/webcam1_live.jpg" alt="Webcam Lounge zum Padel Center Court" title="Webcam Lounge zum Padel Center Court"/>
					</div>
					<div class="webcampadel2">
						<img class="webcambildplatzhalter" src="platzhalter.jpg" alt="Webcam Padelplatz 1" title="Webcam Padelplatz 1"/>
						<img class="webcambildreal" src="padel/webcam2_live.jpg" alt="Webcam Padelplatz 1" title="Webcam Padelplatz 1"/>
					</div>
					<p><i>Padelplätze 2+3+4 (oben), Padelplatz 1 + Center Court (unten).</i></p>
				</div>
			</div>
			<!--
			<div class="container-text">
				<p>Die Riemer-Cam ist ein Projekt, dessen Idee unser lieber Vereinskollege und Herren 40 Mannschaftsspieler Michael Riemer in 2011 hatte. Man solle dadurch von überall sehen, ob die Plätze trocken sind oder ob es gerade regnet. Nachdem Michael nach kurzer schwerer Krankheit 2012 verstarb, wurde sein Projekt 2014 von Nils Gräber aufgegriffen und ihm zu Ehren die Riemer-Cam installiert. In 2024 wurde technologisch aktualisiert, mit Padel erweitert und mit eigener Domain aufgewertet.</p>
			</div>
			-->
		</div>

		<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
		<script src="webcam.js"></script>
	</body>
</html>
';

?>
