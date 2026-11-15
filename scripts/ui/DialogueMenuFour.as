// FAL-865 / FAL-894. Our ActionScript. Not decompiled from either game. Not a compiled movie.
// PC PASS §1b: Subscribe(DialogueListData, onChoiceListUpdate).
// Bind four slots to aChoices[0..3].sChoiceText.
// On select send DialogueMenu_OnDialogueSelect { selectedIndex: uEntryID }.
// Compile with playerglobal only: look up the host shuttle at runtime; create fo4sfOpt* here.
package
{
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.MovieClip;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.utils.getDefinitionByName;

    [SWF(width="1920", height="1080", frameRate="30")]
    public dynamic class DialogueMenuFour extends MovieClip
    {
        public static const KEEP_MENU:String = "DialogueMenu";
        public static const HOST_ROOT:String = "Menu_mc";
        public static const HOST_LIST:String = "DialogueList_mc";
        public static const HOST_LIST_ENTRY:String = "DialogueScrollingListEntry";
        public static const SHUTTLE_MANAGER:String = "BSUIDataManager";
        public static const SHUTTLE_CONNECTOR:String = "UIDataShuttleConnector";
        public static const SUBSCRIBE:String = "Subscribe";
        public static const DISPATCH:String = "Dispatch";
        public static const LIST_PROVIDER:String = "DialogueListData";
        public static const CHOICES:String = "aChoices";
        public static const CHOICE_TEXT:String = "sChoiceText";
        public static const CAN_CHOOSE:String = "bCanBeChosen";
        public static const ALREADY_SAID:String = "bWasAlreadySaid";
        public static const ENTRY_ID:String = "uEntryID";
        public static const ON_SELECT:String = "DialogueMenu_OnDialogueSelect";
        public static const SELECT_KEY:String = "selectedIndex";
        public static const ON_LIST_VIS:String = "DialogueMenu_OnListVisibilityChange";
        public static const LIST_VIS_KEY:String = "isVisible";
        public static const SLOTS:Array = ["fo4sfOptN", "fo4sfOptE", "fo4sfOptS", "fo4sfOptW"];
        public static const HOST_CHILD_NAMES:Array = [
            "DialogueList_mc",
            "PersuasionList_mc",
            "PersuasionData_mc",
            "ButtonBar_mc",
            "CrewSkillsWidget_mc",
            "PrecognitionData_mc"
        ];
        public static const MAP_ROWS:int = 4;
        public static const SLOT_W:int = 420;
        public static const SLOT_H:int = 90;
        public static const SLOT_X:Array = [750, 1240, 750, 260];
        public static const SLOT_Y:Array = [170, 495, 820, 495];
        public static const SLOT_COLOR:uint = 0x1AFF80;

        public var lastChoices:Array;
        public var Menu_mc:MovieClip;
        public var DialogueList_mc:MovieClip;
        public var PersuasionList_mc:MovieClip;
        public var PersuasionData_mc:MovieClip;
        public var ButtonBar_mc:MovieClip;
        public var CrewSkillsWidget_mc:MovieClip;
        public var PrecognitionData_mc:MovieClip;

        public function DialogueMenuFour()
        {
            lastChoices = [];
            ensureHostRoots();
            ensureSlots();
            var mgr:Object = shuttle();
            if (mgr != null)
            {
                mgr.Subscribe(LIST_PROVIDER, onChoiceListUpdate);
            }
        }

        public function onChoiceListUpdate(data:Object):void
        {
            var src:Object = data;
            if (data != null && data.data != null && data.aChoices == null)
            {
                src = data.data;
            }
            lastChoices = (src != null && src.aChoices is Array) ? (src.aChoices as Array) : [];
            var i:int = 0;
            while (i < MAP_ROWS)
            {
                var row:Object = (i < lastChoices.length) ? lastChoices[i] : null;
                var text:String = (row != null && row.sChoiceText != null) ? String(row.sChoiceText) : "";
                fillSlot(SLOTS[i], text);
                i++;
            }
        }

        public function selectSlot(i:int):void
        {
            if (lastChoices == null || i < 0 || i >= MAP_ROWS || i >= lastChoices.length)
            {
                return;
            }
            var row:Object = lastChoices[i];
            if (row == null || row[ENTRY_ID] == null)
            {
                return;
            }
            var payload:Object = {};
            payload[SELECT_KEY] = row[ENTRY_ID];
            sendSelect(ON_SELECT, payload);
        }

        public function fillSlot(name:String, text:String):void
        {
            var value:String = (text == null) ? "" : text;
            var clip:DisplayObject = this.getChildByName(name);
            if (clip == null)
            {
                var idx:int = slotIndex(name);
                if (idx < 0)
                {
                    return;
                }
                clip = makeSlot(idx);
            }
            if (clip is TextField)
            {
                (clip as TextField).text = value;
                return;
            }
            if (clip is DisplayObjectContainer)
            {
                var box:DisplayObjectContainer = clip as DisplayObjectContainer;
                var i:int = 0;
                while (i < box.numChildren)
                {
                    var child:DisplayObject = box.getChildAt(i);
                    if (child is TextField)
                    {
                        (child as TextField).text = value;
                        return;
                    }
                    i++;
                }
            }
        }

        public function sendSelect(eventName:String, payload:Object):void
        {
            if (eventName != ON_SELECT || payload == null || payload[SELECT_KEY] == null)
            {
                return;
            }
            var mgr:Object = shuttle();
            if (mgr == null)
            {
                return;
            }
            mgr.Dispatch(eventName, payload);
        }

        private function shuttle():Object
        {
            try
            {
                return getDefinitionByName(SHUTTLE_MANAGER);
            }
            catch (err:Error)
            {
                return null;
            }
            return null;
        }

        private function ensureHostRoots():void
        {
            // PC FAIL 48a3eb3d: fo4sfOpt* only. FAL-917: Menu_mc is the movie root;
            // DialogueList_mc must be a child of that root, not of a nested clip.
            try
            {
                this.name = HOST_ROOT;
            }
            catch (err:Error)
            {
                // Timeline-placed document root may refuse a name write (Error #2078).
            }
            this.Menu_mc = this;
            var i:int = 0;
            while (i < HOST_CHILD_NAMES.length)
            {
                var n:String = HOST_CHILD_NAMES[i];
                var mc:MovieClip = this.getChildByName(n) as MovieClip;
                if (mc == null)
                {
                    mc = new MovieClip();
                    mc.name = n;
                    mc.mouseEnabled = false;
                    mc.mouseChildren = false;
                    addChild(mc);
                }
                this[n] = mc;
                i++;
            }
        }

        private function ensureSlots():void
        {
            var i:int = 0;
            while (i < MAP_ROWS)
            {
                if (this.getChildByName(SLOTS[i]) == null)
                {
                    makeSlot(i);
                }
                i++;
            }
        }

        private function makeSlot(i:int):TextField
        {
            var tf:TextField = new TextField();
            var fmt:TextFormat = new TextFormat();
            fmt.font = "_sans";
            fmt.size = 28;
            fmt.color = SLOT_COLOR;
            tf.name = SLOTS[i];
            tf.x = SLOT_X[i];
            tf.y = SLOT_Y[i];
            tf.width = SLOT_W;
            tf.height = SLOT_H;
            tf.background = true;
            tf.backgroundColor = 0x101010;
            tf.selectable = false;
            tf.multiline = true;
            tf.wordWrap = true;
            tf.embedFonts = false;
            tf.defaultTextFormat = fmt;
            tf.text = "";
            tf.addEventListener(MouseEvent.CLICK, onSlotClick);
            addChild(tf);
            return tf;
        }

        private function slotIndex(name:String):int
        {
            var i:int = 0;
            while (i < MAP_ROWS)
            {
                if (SLOTS[i] == name)
                {
                    return i;
                }
                i++;
            }
            return -1;
        }

        private function onSlotClick(e:MouseEvent):void
        {
            if (e == null || e.currentTarget == null)
            {
                return;
            }
            selectSlot(slotIndex(e.currentTarget.name));
        }
    }
}
