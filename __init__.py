import unrealsdk
import webbrowser
from typing import Dict, List, Optional

from Mods.ModMenu import (
    EnabledSaveType,
    Game,
    Hook,
    Keybind,
    KeybindManager,
    Mods,
    ModTypes,
    RegisterMod,
    SDKMod,
)

try:
    from Mods.EridiumLib import (
        getLatestVersion,
        getSkillManager,
        getVaultHunterClassName,
        isLatestRelease,
        log,
    )
    from Mods.EridiumLib.keys import KeyBinds
except ModuleNotFoundError or ImportError:
    webbrowser.open("https://github.com/RLNT/bl2_eridium#-troubleshooting")
    raise

if __name__ == "__main__":
    import importlib
    import sys

    importlib.reload(sys.modules["Mods.EridiumLib"])
    importlib.reload(sys.modules["Mods.EridiumLib.keys"])

    # See https://github.com/bl-sdk/PythonSDK/issues/68
    try:
        raise NotImplementedError
    except NotImplementedError:
        __file__ = sys.exc_info()[-1].tb_frame.f_code.co_filename  # type: ignore


class DeathtrapShield(SDKMod):
    # region Mod Info
    Name: str = "Deathtrap Shield"
    Author: str = "Relentless"
    Description: str = "Gives Deathtrap its own configurable shield from the inventory of Gaige."
    Version: str = "1.0.0"

    SupportedGames: Game = Game.BL2
    Types: ModTypes = ModTypes.Utility
    SaveEnabledState: EnabledSaveType = EnabledSaveType.LoadWithSettings

    SettingsInputs: Dict[str, str] = {
        KeyBinds.Enter.value: "Enable",
        KeyBinds.G.value: "GitHub",
        KeyBinds.D.value: "Discord",
    }
    # endregion Mod Info

    _BlockFunStats: bool = False

    # region Mod Setup
    def __init__(self) -> None:
        super().__init__()
        self._shieldHotkey: Keybind = Keybind(
            "Set Deathtrap Shield",
            "S",
            True,
        )
        self.Keybinds = [self._shieldHotkey]

    def Enable(self) -> None:
        super().Enable()
        log(self, f"Version: {self.Version}")

        """
        Version Checking
        """
        latest_version = getLatestVersion("RLNT/bl2_deathtrapshield")
        log(
            self,
            f"Latest release tag: {latest_version}",
        )
        if isLatestRelease(latest_version, self.Version):
            log(self, "Up-to-date")
        else:
            log(self, "There is a newer version available {latest_version}")

    def SettingsInputPressed(self, action: str) -> None:
        """
        Handles the hotkey input in the Mod Menu.
        """
        if action == "GitHub":
            webbrowser.open("https://github.com/RLNT/bl2_deathtrapshield")
        elif action == "Discord":
            webbrowser.open("https://discord.com/invite/Q3qxws6")
        else:
            super().SettingsInputPressed(action)

    # endregion Mod Setup

    # region Helper Functions
    def _isValidShield(self, item: unrealsdk.UObject) -> bool:
        """
        Checks if the passed in item is a valid shield.
        """
        if item is None:
            return False
        if item.Class is None or item.Class.Name != "WillowShield":
            return False

        return True

    def _isShieldSharing(
        self, playerController: unrealsdk.UObject, shareShieldsSkill: unrealsdk.UObject
    ) -> bool:
        """
        Checks if the shield sharing skill is unlocked.
        """
        skillManager: unrealsdk.UObject = getSkillManager()
        return (
            skillManager is not None
            and skillManager.IsSkillActive(playerController, shareShieldsSkill) is True
        )

    def _resetShield(
        self, shield: unrealsdk.UObject, checkClassName: bool, className: Optional[str] = ""
    ) -> None:
        """
        Resets a DT shield of someone who is not a Mechromancer.
        """
        if checkClassName is True and className == "Mechromancer":
            return
        if shield.GetMark() == 3:
            shield.SetMark(1)

    def _resetEquippedShield(self, playerPawn: unrealsdk.UObject) -> None:
        """
        Resets the currently equipped shield if it's a DT shield.
        """
        equippedShield: unrealsdk.UObject = playerPawn.EquippedItems
        if equippedShield is None:
            return
        if self._isValidShield(equippedShield) is True and equippedShield.GetMark() == 3:
            self._resetShield(equippedShield, False)

    def _resetAllShields(self, shield: unrealsdk.UObject, playerPawn: unrealsdk.UObject) -> None:
        """
        Resets all shields in the inventory except for the new DT shield.
        """
        backpackInventory: List[unrealsdk.UObject] = playerPawn.InvManager.Backpack
        if backpackInventory is None:
            return

        for item in backpackInventory:
            if self._isValidShield(item) is True and item.GetMark() == 3 and item != shield:
                self._resetShield(item, False)

        self._resetEquippedShield(playerPawn)

    # endregion Helper Functions

    # region Item Handling
    @Hook("WillowGame.DeathtrapActionSkill.TryToShareShields")
    def _tryToShareShields(
        self,
        caller: unrealsdk.UObject,
        function: unrealsdk.UFunction,
        params: unrealsdk.FStruct,
    ) -> bool:
        """
        Handles the sharing of the shield between
        Gaige and Deathtrap. This would normally
        pick the equipped shield.
        """

        # map the parameter to readable variables and make sure they exist
        playerController: unrealsdk.UObject = params.TheController
        playerPawn: unrealsdk.UObject = params.TheWillowPawn
        deathTrap: unrealsdk.UObject = caller.DeathTrap

        if playerController is None or playerPawn is None or deathTrap is None:
            return True

        # check if the shield sharing skill is unlocked
        if self._isShieldSharing(playerController, caller.ShareShieldsSkill) is False:
            return True

        # get the backpack inventory
        backpackInventory: List[unrealsdk.UObject] = playerPawn.InvManager.Backpack
        if backpackInventory is None:
            return True

        """
        Iterate through the items in the backpack and check for shields.
        If a shield is marked as DT shield, it will be picked.
        This iterates from bottom to top because the slots in the backpack
        are indexed descending for whatever reason.
        """
        shield = None
        for item in backpackInventory:
            if self._isValidShield(item) is False:
                continue
            if item.GetMark() == 3:
                shield = item
                break

        """
        Make sure the shield is also usable by the player or you could give
        Deathtrap a completely overleveled shield.
        """
        if shield is None or shield.CanBeUsedBy(playerPawn) is False:
            return True

        """
        Only give Deathtrap a clone of the shield so it's not consumed.
        """
        shieldClone: unrealsdk.UObject = shield.CreateClone()
        if shieldClone is None:
            return True

        """
        Make the shield undroppable in case DT dies to prevent duping.
        Then give the shield to Deathtrap.
        """
        shieldClone.bDropOnDeath = False
        shieldClone.GiveTo(deathTrap, True)

        # don't call the original function since we handled everything ourselves
        return False

    # endregion Item Handling

    # region Hotkey Handling
    @Hook("WillowGame.StatusMenuInventoryPanelGFxObject.NormalInputKey")
    def _normalInputKey(
        self,
        caller: unrealsdk.UObject,
        function: unrealsdk.UFunction,
        params: unrealsdk.FStruct,
    ) -> bool:
        """
        Handles the hotkey input on the inventory screen.
        Only checks the input, doesn't affect the tooltips.
        """

        # only listen to key presses
        if params.uevent != KeybindManager.InputEvent.Pressed:
            return True

        # wait until the inventory screen's setup is done
        if caller.bInitialSetupFinished is False:
            return True

        # prevents hotkey usages on swapping or comparing
        if caller.SwitchToQueuedInputHandler(params.ukey, params.uevent):
            return True

        # only allow the hotkey in the backpack panel
        if caller.bInEquippedView is True:
            return True

        # only accept hotkey when the player is a Mechromancer
        playerController: unrealsdk.UObject = caller.ParentMovie.WPCOwner
        if getVaultHunterClassName(playerController) != "Mechromancer":
            return True

        """
        If the modded hotkey is pressed, get the selected item, check if it's
        a valid shield and change its mark depending on the previous mark.
        Also change all other shields to default when a new DT shield is chosen.
        """
        if params.ukey == self._shieldHotkey.Key:
            item: unrealsdk.UObject = caller.GetSelectedThing()

            if self._isValidShield(item) is False:
                return True

            # save the state so it doesn't switch to the first item again
            caller.BackpackPanel.SaveState()

            if item.GetMark() == 3:
                item.SetMark(1)
            else:
                item.SetMark(3)
                self._resetAllShields(item, playerController.MyWillowPawn)

            # refresh the inventory screen
            caller.ParentMovie.RefreshInventoryScreen(True)

            # restore the old state
            if caller.bInEquippedView is False:
                caller.BackpackPanel.RestoreState()

            # don't call the original function since we handled our hotkey
            return False

        # if it was some other hotkey which passed the checks, call the original function
        return True

    # endregion Hotkey Handling

    # region Text Editing
    @Hook("WillowGame.StatusMenuInventoryPanelGFxObject.SetTooltipText")
    def _setTooltipText(
        self,
        caller: unrealsdk.UObject,
        function: unrealsdk.UFunction,
        params: unrealsdk.FStruct,
    ) -> bool:
        """
        Handles the hotkey tooltips on the inventory screen.
        Appends our custom hotkey to the end of the original text
        so it still can be localized.
        Only changes the text, doesn't affect the hotkeys.
        """

        # only change the text in the backpack panel
        if caller.bInEquippedView is True:
            return True

        # only change the text when the player is a Mechromancer
        playerController: unrealsdk.UObject = caller.ParentMovie.WPCOwner
        if getVaultHunterClassName(playerController) != "Mechromancer":
            return True

        # only change the text if the item is a valid shield
        item: unrealsdk.UObject = caller.GetSelectedThing()
        if self._isValidShield(item) is False:
            return True

        """
        Get the original hotkey text and append our hotkey.
        The hotkey text changes depending if it's already set as DT shield.
        """
        result: str = ""
        if item.GetMark() == 3:
            result = f"{params.TooltipsText}\n[{self._shieldHotkey.Key}] Unset Deathtrap Shield"
        else:
            result = f"{params.TooltipsText}\n[{self._shieldHotkey.Key}] Set Deathtrap Shield"

        """
        Since we only append our changes to the original text, we need
        to pass our new text as a parameter to the original function.
        Don't call it again afterwards or changes would be overwritten.
        """
        caller.SetTooltipText(result)
        return False

    @Hook("WillowGame.WillowPlayerController.ShowStatusMenu")
    def _showStatusMenu(
        self, caller: unrealsdk.UObject, function: unrealsdk.UFunction, params: unrealsdk.FStruct
    ) -> bool:
        """
        Handles executing Console Commands since there is a string bug.
        https://github.com/bl-sdk/PythonSDK/issues/28
        """

        # edit the skill description of the shield sharing ability
        _skillDescription: List[str] = [
            "Gives [skill]Deathtrap[-skill] a copy of a configurable",
            "[skill]shield[-skill] from your inventory.",
        ]
        currentDescription: str = unrealsdk.FindObject(
            "SkillDefinition", "GD_Tulip_Mechromancer_Skills.BestFriendsForever.SharingIsCaring"
        ).SkillDescription
        if currentDescription != " ".join(_skillDescription):
            log(instance, "called")
            caller.ConsoleCommand(
                "set SkillDefinition'GD_Tulip_Mechromancer_Skills.BestFriendsForever."
                "SharingIsCaring' SkillDescription " + " ".join(_skillDescription)
            )

        return True

    @Hook("WillowGame.ItemCardGFxObject.SetItemCardEx")
    def _setItemCardEx(
        self, caller: unrealsdk.UObject, function: unrealsdk.UFunction, params: unrealsdk.FStruct
    ) -> bool:
        """
        Handles the item info cards descriptions in the inventory screen.
        Appends our custom text to the end of the original text
        so it still can be localized.
        Credits: apple
        """

        # only change the text if the item is a valid DT shield
        item: unrealsdk.UObject = params.InventoryItem.ObjectPointer
        if self._isValidShield(item) is False or item.GetMark() != 3:
            return True

        """
        Since this is called quite often, we can use this to reset the
        shield if someone has the shield who is not a Mechromancer.
        Also we can reset the status of equipped shields.
        This shouldn't happen since the status is lost when it's being
        thrown away but just in case.
        """
        playerController: unrealsdk.UObject = params.WPC
        className: str = getVaultHunterClassName(playerController)
        self._resetShield(item, True, className)
        self._resetEquippedShield(playerController.MyWillowPawn)

        # prevent showing DT shield status if no Mechromancer
        if className != "Mechromancer":
            return True

        # append our status to the original text
        text = item.GenerateFunStatsText()
        if text is None:
            text = ""

        text += '<font color="#00FF9C">'
        text += "• Current Deathtrap Shield"
        text += "</font>"

        """
        The hooked function is pretty complex so before replicating its logic,
        we pass our modified text to it but block it from overwriting.
        """
        caller.SetFunStats(text)
        self._BlockFunStats = True
        return True

    @Hook("WillowGame.ItemCardGFxObject.SetFunStats")
    def _setFunStats(
        self, caller: unrealsdk.UObject, function: unrealsdk.UFunction, params: unrealsdk.FStruct
    ) -> bool:
        """
        Handles blocking the overwriting of item card descriptions if we changed it.
        Credits: apple
        """
        if self._BlockFunStats:
            self._BlockFunStats = False
            return False
        return True

    # endregion Text Editing


instance = DeathtrapShield()
if __name__ == "__main__":
    log(instance, "Manually loaded")
    for mod in Mods:
        if mod.Name == instance.Name:
            if mod.IsEnabled:
                mod.Disable()
            Mods.remove(mod)
            log(instance, "Removed last instance")

            # Fixes inspect.getfile()
            instance.__class__.__module__ = mod.__class__.__module__
            break
RegisterMod(instance)
