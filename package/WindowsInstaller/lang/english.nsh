/*
FuCadUp Installer Language File
Language: English
*/

!insertmacro LANGFILE_EXT "English"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Installed for Current User)"

${LangFileString} TEXT_WELCOME "This wizard will guide you through the installation of $(^NameDA). $\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Compiling Python scripts..."

${LangFileString} TEXT_FINISH_DESKTOP "Create desktop shortcut"
${LangFileString} TEXT_FINISH_WEBSITE "Visit github.com/otherworld-dev/FuCadUp for the latest news, support and tips"

#${LangFileString} FileTypeTitle "FuCadUp-Document"

#${LangFileString} SecAllUsersTitle "Install for all users?"
${LangFileString} SecFileAssocTitle "File associations"
${LangFileString} SecDesktopTitle "Desktop icon"

${LangFileString} SecCoreDescription "The FuCadUp files."
#${LangFileString} SecAllUsersDescription "Install FuCadUp for all users or just the current user."
${LangFileString} SecFileAssocDescription "Files with a .FCStd extension will automatically open in FuCadUp."
${LangFileString} SecDesktopDescription "A FuCadUp icon on the desktop."
#${LangFileString} SecDictionaries "Dictionaries"
#${LangFileString} SecDictionariesDescription "Spell-checker dictionaries that can be downloaded and installed."

#${LangFileString} PathName 'Path to the file $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'The file $\"xxx.exe$\" is not in the specified path.'

#${LangFileString} DictionariesFailed 'Download of dictionary for language $\"$R3$\" failed.'

#${LangFileString} ConfigInfo "The following configuration of FuCadUp could take a while."

#${LangFileString} RunConfigureFailed "Could not run configure script."
${LangFileString} InstallRunning "The installer is already running!"
${LangFileString} AlreadyInstalled "FuCadUp ${APP_SERIES_KEY2} is already installed!$\r$\n\
				Do you nevertheless want to install FuCadUp over the existing version?"
${LangFileString} NewerInstalled "You are trying to install an older version of FuCadUp than what you have installed.$\r$\n\
				  If you really want this, you must uninstall the existing FuCadUp $OldVersionNumber before."

#${LangFileString} FinishPageMessage "Congratulations! FuCadUp has been installed successfully.$\r$\n\
#					$\r$\n\
#					(The first start of FuCadUp might take some seconds.)"
${LangFileString} FinishPageRun "Launch FuCadUp"

${LangFileString} UnNotInRegistryLabel "Unable to find FuCadUp in the registry.$\r$\n\
					Shortcuts on the desktop and in the Start Menu will not be removed."
${LangFileString} UnInstallRunning "You must close FuCadUp first!"
${LangFileString} UnNotAdminLabel "You must have administrator privileges to uninstall FuCadUp!"
${LangFileString} UnReallyRemoveLabel "Are you sure you want to completely remove FuCadUp and all of its components?"
${LangFileString} UnFuCadUpPreferencesTitle 'FuCadUp$\'s user preferences'

#${LangFileString} SecUnProgDescription "Uninstalls xxx."
${LangFileString} SecUnPreferencesDescription 'Deletes FuCadUp$\'s configuration$\r$\n\
						(folder $\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						for you or for all users (if you are admin).'
${LangFileString} DialogUnPreferences 'You chose to delete the FuCadUp user configuration.$\r$\n\
						This will also delete all installed FuCadUp addons, and will affect the$\r$\n\
						preferences for all versions of FuCadUp.$\r$\n\
						Are you sure you want to proceed?'
${LangFileString} SecUnProgramFilesDescription "Uninstall FuCadUp and all of its components."

${LangFileString} DirNotEmptyWarning "The selected folder '$INSTDIR' is not empty.$\r$\n\
                        The installer will remove all its content before installing. Continue?"
${LangFileString} RMInstDirFailed "Failed to remove '$INSTDIR'.$\r$\n\
                        Make sure you have sufficient permissions and that no files are in use."
