#!/usr/bin/env python3
"""Builds content/translations/{ru,pt,bn}.json -- the words shown during salaah.

    python3 tools/add_salaah_languages.py            # say what it would write
    python3 tools/add_salaah_languages.py --write

WHY THESE THREE WERE MISSING. Russian, Portuguese and Bengali were added to the mat as
INTERFACE languages: menus, buttons, labels, all ten packs complete. The words a child reads
while actually praying live somewhere else -- content/translations/<lang>.json -- and nobody
ever wrote one. Translation.for_key then returns None for every passage and the step screen
shows the Arabic with nothing under it. A child praying in Bengali got no meaning at all.

WHERE EACH PART COMES FROM, which is not the same for all three.

    pt   The five Qur'anic passages are NOT here. Portuguese already has a complete licensed
         Qur'an on the mat -- Helmi Nasr, from QuranEnc's official export under the permission
         Harry was granted -- so tools/retext_salaah_quran.py takes them from that, the same
         way it does for English, Spanish, Hindi and Chinese. Run that tool after this one.

    ru   Drafted, including the Qur'anic passages, AND THAT IS A SECOND CHOICE. A public-domain
         Russian Qur'an exists: Sablukov, 1878, the first made from the Arabic, out of
         copyright beyond argument, and it is the obvious thing to use -- French and Urdu both
         take their Qur'anic lines from public-domain translations exactly like it. It was
         fetched and rejected. Every Russian edition in the source that supplied the Urdu
         (fawazahmed0/quran-api) has been transcribed with the sentence-ending punctuation
         stripped and the opening quotation marks never closed: `Скажи: "Он - Бог - един` with
         no full stop and no closing quote, in all of Sablukov, Krachkovsky and Osmanov. The
         Urdu from the same place is clean, so it is those editions and not the source. Using
         them would mean repairing a published translation by hand and printing the result
         under its translator's name. The drafts below can be thrown away the day a properly
         transcribed Russian edition turns up.

    bn   Drafted, and this one has a known better answer waiting. QuranEnc carries a Bengali
         translation under the same permission that gave the mat its English, Spanish, Hindi,
         Portuguese and Chinese, but quranenc.com cannot be reached from here. One session with
         a browser would replace the six Qur'anic passages with a publisher-reviewed edition.

WHAT "DRAFTED" MEANS, and it means exactly what it means for the six languages already
shipping. Written here, by an AI, from the English. Not checked by anyone who reads the
language. Not checked by anyone qualified in the religion. Every line is marked
"written for this app (draft, needs review)" in sources, the file says so in about, and the mat
says so on its Sources page. English, Spanish, Hindi and Chinese shipped on exactly this
footing from v0.47; this is not a lower standard than the mat already holds, and it is a long
way below the standard the mat should eventually hold.

THE VOCABULARY, decided per language and worth knowing because a reviewer will have opinions:
    pt   "Allah", matching Helmi Nasr, whose text sits in the same screen.
    ru   "Аллах", modern Russian Muslim usage, used in every passage so one screen has one
         voice. Sablukov writes "Бог"; had his text been usable, this would have followed it,
         the way French follows Kazimirski's "Dieu" into its drafted du'as.
    bn   "আল্লাহ", standard Bengali Muslim usage.

intention, kinds and prayers are not translated here. They already exist, translated, in each
language's pack.json, and are copied from there rather than written twice.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

NAMES = {
    "ru": ("Russian", "Русский", "ltr"),
    "pt": ("Portuguese", "Português", "ltr"),
    "bn": ("Bengali", "বাংলা", "ltr"),
}

DRAFT = "written for this app (draft, needs review)"

LINES: dict[str, dict[str, list[str]]] = {

    "pt": {
        "takbir": ["Allah é o maior."],
        "allahu_akbar": ["Allah é o maior."],
        "subhanallah": ["Glória a Allah."],
        "alhamdulillah": ["Todo louvor pertence a Allah."],
        "istighfar": ["Peço perdão a Allah."],
        "ameen": ["Ó Allah, atende a nossa súplica."],
        "jalsa_dua": ["Meu Senhor, perdoa-me."],
        "ruku_tasbih": ["Glória ao meu Senhor, o Magnífico."],
        "sujood_tasbih": ["Glória ao meu Senhor, o Altíssimo."],
        "salam": ["Que a paz esteja convosco, e a misericórdia de Allah."],
        "taawwudh_basmala": ["Refugio-me em Allah contra Satanás, o maldito."],
        "istiftah": [
            "Glória a Ti, ó Allah, e todo louvor é Teu.",
            "Bendito seja o Teu nome e exaltada a Tua majestade.",
            "Não há divindade além de Ti.",
        ],
        "tasmi_tahmid": [
            "Allah ouve quem O louva.",
            "Nosso Senhor, a Ti pertence todo louvor.",
        ],
        "rabbana_atina": [
            "Nosso Senhor, concede-nos o bem neste mundo",
            "e o bem na outra vida, e protege-nos do castigo do Fogo.",
        ],
        "dhikr_salam": [
            "Ó Allah, Tu és a Paz e de Ti vem a paz.",
            "Bendito sejas, ó Dono da majestade e da honra.",
        ],
        "dhikr_tahlil": [
            "Não há divindade além de Allah, único, sem associado.",
            "Dele é o domínio e Dele é o louvor,",
            "e Ele tem poder sobre todas as coisas.",
        ],
        "tashahhud": [
            "Todas as saudações, as orações e as boas obras pertencem a Allah.",
            "Que a paz esteja contigo, ó Profeta, e a misericórdia de Allah e as Suas bênçãos.",
            "Que a paz esteja sobre nós e sobre os servos virtuosos de Allah.",
            "Testemunho que não há divindade além de Allah, e que Muhammad é Seu servo e Seu "
            "mensageiro.",
        ],
        "salawat": [
            "Ó Allah, concede a Tua graça a Muhammad e à família de Muhammad,",
            "como a concedeste a Abraão e à família de Abraão. Tu és Digno de louvor, Glorioso.",
            "Ó Allah, abençoa Muhammad e a família de Muhammad,",
            "como abençoaste Abraão e a família de Abraão. Tu és Digno de louvor, Glorioso.",
        ],
        "qunut_1": [
            "Ó Allah, pedimos-Te ajuda, pedimos o Teu perdão, cremos em Ti e em Ti confiamos.",
            "Louvamos-Te por todo o bem, agradecemos-Te e não somos ingratos para contigo.",
            "Afastamo-nos e deixamos quem Te desobedece.",
        ],
        "qunut_2": [
            "Ó Allah, só a Ti adoramos; para Ti rezamos e nos prostramos.",
            "A Ti nos esforçamos e acorremos. Esperamos a Tua misericórdia e tememos o Teu "
            "castigo.",
            "O Teu castigo certamente alcança os que rejeitam a fé.",
        ],
        "ayat_kursi": [
            "Allah: não há divindade além d'Ele, o Vivente, Aquele que a tudo sustenta.",
            "Não O acometem nem a sonolência nem o sono.",
            "A Ele pertence o que há nos céus e o que há na terra.",
            "Quem poderia interceder junto d'Ele senão com a Sua permissão?",
            "Ele sabe o que está diante deles e o que está atrás deles,",
            "e nada abarcam do Seu conhecimento senão o que Ele quer.",
            "O Seu Trono abrange os céus e a terra,",
            "e preservá-los não O fatiga.",
            "Ele é o Altíssimo, o Magnífico.",
        ],
    },

    "ru": {
        "takbir": ["Аллах велик."],
        "allahu_akbar": ["Аллах велик."],
        "subhanallah": ["Слава Аллаху."],
        "alhamdulillah": ["Вся хвала принадлежит Аллаху."],
        "istighfar": ["Прошу прощения у Аллаха."],
        "ameen": ["О Аллах, ответь на нашу молитву."],
        "jalsa_dua": ["Господь мой, прости меня."],
        "ruku_tasbih": ["Слава Господу моему Великому."],
        "sujood_tasbih": ["Слава Господу моему Всевышнему."],
        "salam": ["Мир вам и милость Аллаха."],
        "taawwudh_basmala": ["Прибегаю к защите Аллаха от сатаны, побиваемого камнями."],
        "istiftah": [
            "Слава Тебе, о Аллах, и вся хвала Тебе.",
            "Благословенно имя Твоё и возвышено величие Твоё.",
            "Нет божества, кроме Тебя.",
        ],
        "tasmi_tahmid": [
            "Аллах слышит того, кто восхваляет Его.",
            "Господь наш, Тебе вся хвала.",
        ],
        "rabbana_atina": [
            "Господь наш, даруй нам благо в этом мире",
            "и благо в мире ином, и защити нас от наказания Огня.",
        ],
        "dhikr_salam": [
            "О Аллах, Ты — Мир, и от Тебя исходит мир.",
            "Благословен Ты, Обладатель величия и почёта.",
        ],
        "dhikr_tahlil": [
            "Нет божества, кроме одного Аллаха, нет у Него сотоварища.",
            "Ему принадлежит власть и Ему хвала,",
            "и Он над всякой вещью властен.",
        ],
        "tashahhud": [
            "Все приветствия, молитвы и благие дела принадлежат Аллаху.",
            "Мир тебе, о Пророк, и милость Аллаха и Его благословения.",
            "Мир нам и праведным рабам Аллаха.",
            "Свидетельствую, что нет божества, кроме Аллаха, и что Мухаммад — Его раб и Его "
            "посланник.",
        ],
        "salawat": [
            "О Аллах, ниспошли Свою милость Мухаммаду и семье Мухаммада,",
            "как Ты ниспослал её Ибрахиму и семье Ибрахима. Воистину, Ты Достохвальный, "
            "Славный.",
            "О Аллах, благослови Мухаммада и семью Мухаммада,",
            "как Ты благословил Ибрахима и семью Ибрахима. Воистину, Ты Достохвальный, Славный.",
        ],
        "qunut_1": [
            "О Аллах, мы просим у Тебя помощи, просим у Тебя прощения, веруем в Тебя и на Тебя "
            "уповаем.",
            "Мы восхваляем Тебя за всё благо, благодарим Тебя и не отрекаемся от Тебя.",
            "Мы оставляем и покидаем того, кто Тебе не повинуется.",
        ],
        "qunut_2": [
            "О Аллах, Тебе одному мы поклоняемся; Тебе молимся и пред Тобою падаем ниц.",
            "К Тебе стремимся и спешим. Надеемся на Твою милость и боимся Твоего наказания.",
            "Воистину, Твоё наказание постигает отвергающих веру.",
        ],
        "ayat_kursi": [
            "Аллах — нет божества, кроме Него, Живого, Вседержителя.",
            "Не овладевают Им ни дремота, ни сон.",
            "Ему принадлежит то, что на небесах, и то, что на земле.",
            "Кто станет заступаться перед Ним без Его дозволения?",
            "Он знает то, что перед ними, и то, что позади них,",
            "а они постигают из Его знания только то, что Он пожелает.",
            "Престол Его объемлет небеса и землю,",
            "и не тяготит Его охрана их.",
            "Он — Всевышний, Великий.",
        ],
        "fatiha": [
            "Во имя Аллаха, Милостивого, Милосердного.",
            "Хвала Аллаху, Господу миров,",
            "Милостивому, Милосердному,",
            "Владыке Дня воздаяния.",
            "Тебе одному мы поклоняемся и Тебя одного просим о помощи.",
            "Веди нас прямым путём,",
            "путём тех, кого Ты облагодетельствовал, не тех, на кого пал гнев, и не "
            "заблудших.",
        ],
        "kawthar": [
            "Во имя Аллаха, Милостивого, Милосердного.",
            "Воистину, Мы даровали тебе изобилие.",
            "Посему совершай молитву ради своего Господа и приноси жертву.",
            "Воистину, твой ненавистник сам окажется лишённым.",
        ],
        "ikhlas": [
            "Во имя Аллаха, Милостивого, Милосердного.",
            "Скажи: Он — Аллах, Един,",
            "Аллах Самодостаточный.",
            "Он не родил и не был рождён,",
            "и нет никого, равного Ему.",
        ],
        "falaq": [
            "Во имя Аллаха, Милостивого, Милосердного.",
            "Скажи: прибегаю к защите Господа рассвета",
            "от зла того, что Он сотворил,",
            "от зла мрака, когда он наступает,",
            "от зла дующих на узлы,",
            "и от зла завистника, когда он завидует.",
        ],
        "nas": [
            "Во имя Аллаха, Милостивого, Милосердного.",
            "Скажи: прибегаю к защите Господа людей,",
            "Царя людей,",
            "Бога людей,",
            "от зла искусителя, отступающего при поминании Аллаха,",
            "который наущает в груди людей,",
            "от джиннов и людей.",
        ],
    },

    "bn": {
        "takbir": ["আল্লাহ সবচেয়ে মহান।"],
        "allahu_akbar": ["আল্লাহ সবচেয়ে মহান।"],
        "subhanallah": ["আল্লাহর পবিত্রতা ঘোষণা করি।"],
        "alhamdulillah": ["সমস্ত প্রশংসা আল্লাহর।"],
        "istighfar": ["আমি আল্লাহর কাছে ক্ষমা প্রার্থনা করি।"],
        "ameen": ["হে আল্লাহ, আমাদের প্রার্থনা কবুল করুন।"],
        "jalsa_dua": ["হে আমার প্রতিপালক, আমাকে ক্ষমা করুন।"],
        "ruku_tasbih": ["আমার মহান প্রতিপালকের পবিত্রতা ঘোষণা করি।"],
        "sujood_tasbih": ["আমার সর্বোচ্চ প্রতিপালকের পবিত্রতা ঘোষণা করি।"],
        "salam": ["আপনাদের উপর শান্তি বর্ষিত হোক এবং আল্লাহর রহমত।"],
        "taawwudh_basmala": ["বিতাড়িত শয়তান থেকে আমি আল্লাহর আশ্রয় প্রার্থনা করি।"],
        "istiftah": [
            "হে আল্লাহ, আপনার পবিত্রতা ঘোষণা করি এবং সমস্ত প্রশংসা আপনার।",
            "আপনার নাম বরকতময় এবং আপনার মর্যাদা সুউচ্চ।",
            "আপনি ছাড়া কোনো উপাস্য নেই।",
        ],
        "tasmi_tahmid": [
            "আল্লাহ শোনেন তাকে, যে তাঁর প্রশংসা করে।",
            "হে আমাদের প্রতিপালক, সমস্ত প্রশংসা আপনার।",
        ],
        "rabbana_atina": [
            "হে আমাদের প্রতিপালক, আমাদের এই দুনিয়ায় কল্যাণ দিন",
            "এবং পরকালে কল্যাণ দিন, আর আমাদের আগুনের শাস্তি থেকে রক্ষা করুন।",
        ],
        "dhikr_salam": [
            "হে আল্লাহ, আপনিই শান্তি এবং আপনার কাছ থেকেই শান্তি আসে।",
            "আপনি বরকতময়, হে মহিমা ও সম্মানের অধিকারী।",
        ],
        "dhikr_tahlil": [
            "আল্লাহ ছাড়া কোনো উপাস্য নেই, তিনি একক, তাঁর কোনো শরিক নেই।",
            "রাজত্ব তাঁরই এবং প্রশংসা তাঁরই,",
            "আর তিনি সব কিছুর উপর ক্ষমতাবান।",
        ],
        "tashahhud": [
            "সমস্ত অভিবাদন, নামায ও উত্তম কাজ আল্লাহর জন্য।",
            "হে নবী, আপনার উপর শান্তি বর্ষিত হোক এবং আল্লাহর রহমত ও বরকত।",
            "আমাদের উপর এবং আল্লাহর সৎকর্মশীল বান্দাদের উপর শান্তি বর্ষিত হোক।",
            "আমি সাক্ষ্য দিই যে আল্লাহ ছাড়া কোনো উপাস্য নেই, এবং মুহাম্মদ তাঁর বান্দা ও রাসূল।",
        ],
        "salawat": [
            "হে আল্লাহ, মুহাম্মদ ও মুহাম্মদের পরিবারের উপর অনুগ্রহ বর্ষণ করুন,",
            "যেমন আপনি ইবরাহীম ও ইবরাহীমের পরিবারের উপর অনুগ্রহ বর্ষণ করেছিলেন। নিশ্চয়ই আপনি "
            "প্রশংসিত, মহিমান্বিত।",
            "হে আল্লাহ, মুহাম্মদ ও মুহাম্মদের পরিবারের উপর বরকত দিন,",
            "যেমন আপনি ইবরাহীম ও ইবরাহীমের পরিবারের উপর বরকত দিয়েছিলেন। নিশ্চয়ই আপনি প্রশংসিত, "
            "মহিমান্বিত।",
        ],
        "qunut_1": [
            "হে আল্লাহ, আমরা আপনার কাছে সাহায্য চাই, ক্ষমা চাই, আপনার উপর ঈমান আনি এবং আপনার উপর "
            "ভরসা করি।",
            "আমরা সমস্ত কল্যাণের জন্য আপনার প্রশংসা করি, আপনার শুকরিয়া আদায় করি এবং অকৃতজ্ঞ হই "
            "না।",
            "যে আপনার অবাধ্য হয়, আমরা তাকে ত্যাগ করি ও পরিহার করি।",
        ],
        "qunut_2": [
            "হে আল্লাহ, আমরা কেবল আপনারই ইবাদত করি; আপনার জন্যই নামায পড়ি ও সিজদা করি।",
            "আপনার দিকেই আমরা ছুটে চলি। আমরা আপনার রহমতের আশা করি ও আপনার শাস্তিকে ভয় করি।",
            "নিশ্চয়ই আপনার শাস্তি কাফিরদের উপর পতিত হয়।",
        ],
        "ayat_kursi": [
            "আল্লাহ — তিনি ছাড়া কোনো উপাস্য নেই, তিনি চিরঞ্জীব, সবকিছুর ধারক।",
            "তন্দ্রা ও নিদ্রা তাঁকে স্পর্শ করে না।",
            "আকাশে ও পৃথিবীতে যা কিছু আছে সবই তাঁর।",
            "তাঁর অনুমতি ছাড়া কে তাঁর কাছে সুপারিশ করতে পারে?",
            "তিনি জানেন যা তাদের সামনে আছে এবং যা তাদের পিছনে আছে,",
            "আর তারা তাঁর জ্ঞানের কিছুই আয়ত্ত করতে পারে না, তিনি যা ইচ্ছা করেন তা ছাড়া।",
            "তাঁর কুরসী আকাশ ও পৃথিবীকে পরিব্যাপ্ত করে আছে,",
            "আর এ দুটির রক্ষণাবেক্ষণ তাঁকে ক্লান্ত করে না।",
            "তিনি সর্বোচ্চ, মহান।",
        ],
        "fatiha": [
            "পরম করুণাময় অসীম দয়ালু আল্লাহর নামে।",
            "সমস্ত প্রশংসা আল্লাহর, যিনি সকল জগতের প্রতিপালক,",
            "পরম করুণাময়, অসীম দয়ালু,",
            "বিচার দিনের মালিক।",
            "আমরা কেবল আপনারই ইবাদত করি এবং কেবল আপনারই সাহায্য চাই।",
            "আমাদের সরল পথ দেখান,",
            "তাদের পথ, যাদের আপনি অনুগ্রহ করেছেন; তাদের নয় যাদের উপর ক্রোধ এসেছে, এবং "
            "পথভ্রষ্টদেরও নয়।",
        ],
        "kawthar": [
            "পরম করুণাময় অসীম দয়ালু আল্লাহর নামে।",
            "নিশ্চয়ই আমরা আপনাকে প্রাচুর্য দান করেছি।",
            "অতএব আপনার প্রতিপালকের উদ্দেশ্যে নামায পড়ুন ও কুরবানি করুন।",
            "নিশ্চয়ই আপনার শত্রুই নির্বংশ।",
        ],
        "ikhlas": [
            "পরম করুণাময় অসীম দয়ালু আল্লাহর নামে।",
            "বলুন, তিনি আল্লাহ, এক।",
            "আল্লাহ অমুখাপেক্ষী।",
            "তিনি কাউকে জন্ম দেননি এবং তাঁকেও জন্ম দেওয়া হয়নি,",
            "আর তাঁর সমতুল্য কেউ নেই।",
        ],
        "falaq": [
            "পরম করুণাময় অসীম দয়ালু আল্লাহর নামে।",
            "বলুন, আমি আশ্রয় প্রার্থনা করি ভোরের প্রতিপালকের কাছে,",
            "তিনি যা সৃষ্টি করেছেন তার অনিষ্ট থেকে,",
            "রাতের অন্ধকারের অনিষ্ট থেকে যখন তা ঘনিয়ে আসে,",
            "গিঁটে ফুঁ দেওয়ার অনিষ্ট থেকে,",
            "আর হিংসুকের অনিষ্ট থেকে যখন সে হিংসা করে।",
        ],
        "nas": [
            "পরম করুণাময় অসীম দয়ালু আল্লাহর নামে।",
            "বলুন, আমি আশ্রয় প্রার্থনা করি মানুষের প্রতিপালকের কাছে,",
            "মানুষের অধিপতি,",
            "মানুষের উপাস্য,",
            "কুমন্ত্রণাদাতার অনিষ্ট থেকে, যে পিছিয়ে যায়,",
            "যে মানুষের অন্তরে কুমন্ত্রণা দেয়,",
            "জিন ও মানুষের মধ্য থেকে।",
        ],
    },
}

ABOUT = {
    "pt": ("RASCUNHO / DRAFT. Passagens do Alcorão: Helmi Nasr, a mesma tradução que o ecrã de "
           "leitura do tapete usa, tirada da cópia aqui instalada. O versículo do Trono e as "
           "invocações: redigidos para esta aplicação, a rever por um leitor qualificado. "
           "Nada aqui foi lido por alguém com qualificação."),
    # The English word DRAFT is in each of these on purpose, beside the native one. It is the
    # marker the project checks for -- tests/test_core.py, NewLanguagesTest -- and every
    # shipping translation carries it, so a file written in another script has to as well or it
    # declares itself reviewed by being unreadable to the check.
    "ru": ("ЧЕРНОВИК / DRAFT. Все тексты написаны для этого приложения и требуют проверки "
           "квалифицированным носителем языка. Перевод Саблукова (1878), находящийся в "
           "общественном достоянии, не был использован: во всех доступных русских изданиях "
           "источника отсутствуют знаки конца предложения и не закрыты кавычки. "
           "Ничто здесь не проверено специалистом."),
    "bn": ("খসড়া / DRAFT। সমস্ত পাঠ এই অ্যাপের জন্য লেখা এবং যোগ্য পর্যালোচকের দ্বারা পরীক্ষা করা "
           "প্রয়োজন। কুরআনের অংশগুলি QuranEnc-এর বাংলা অনুবাদ দিয়ে প্রতিস্থাপন করা যেতে পারে। "
           "এখানে কিছুই যোগ্য কারও দ্বারা পড়া হয়নি।"),
}


def arabic_counts() -> dict[str, int]:
    text = json.loads((ROOT / "assets" / "content" / "core" / "arabic.json")
                      .read_text(encoding="utf-8"))["text"]
    return {k: len(v) for k, v in text.items() if isinstance(v, list)}


def from_pack(lang: str) -> dict:
    ui = json.loads((ROOT / "assets" / "content" / "packs" / lang / "pack.json")
                    .read_text(encoding="utf-8"))["ui"]
    return {
        "intention": ui.get("intention", ""),
        "kinds": {k: ui.get(f"kind.{k}", k) for k in ("farz", "sunnah", "nafl", "witr")},
        "prayers": {p: ui.get(f"prayer.{p}", p)
                    for p in ("fajr", "dhuhr", "asr", "maghrib", "isha")},
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="add_salaah_languages", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    want = arabic_counts()
    english = json.loads((ROOT / "assets" / "content" / "translations" / "en.json")
                         .read_text(encoding="utf-8"))["lines"]
    problems = []
    for lang, lines in LINES.items():
        name, native, direction = NAMES[lang]
        # Every passage this language claims must have the number of lines the Arabic has, or
        # the screen silently drops to Arabic alone -- see Translation.for_key.
        for key, got in lines.items():
            if key in want and len(got) != want[key]:
                problems.append(f"{lang}/{key}: {len(got)} lines, the Arabic has {want[key]}")
            if any(not line.strip() for line in got):
                problems.append(f"{lang}/{key}: an empty line")
        missing = sorted(set(english) - set(lines))
        extra = sorted(set(lines) - set(english))
        if extra:
            problems.append(f"{lang}: passages English does not have: {extra}")
        print(f"  {lang} ({native}): {len(lines)} passages, "
              f"{sum(len(v) for v in lines.values())} lines"
              + (f", leaving {len(missing)} to the Qur'an tool: {missing}" if missing else ""))

    if problems:
        print("\n  REFUSING:")
        for p in problems:
            print(f"      {p}")
        return 1

    if not args.write:
        print("\n  Nothing written. Pass --write to do it.")
        return 0

    for lang, lines in LINES.items():
        name, native, direction = NAMES[lang]
        doc = {
            "schema": 1,
            "lang": lang,
            "name": name,
            "nativeName": native,
            "dir": direction,
            "about": ABOUT[lang],
            "sources": {k: DRAFT for k in sorted(lines)},
            **from_pack(lang),
            "lines": {k: lines[k] for k in sorted(lines)},
        }
        where = ROOT / "assets" / "content" / "translations" / f"{lang}.json"
        where.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        back = json.loads(where.read_text(encoding="utf-8"))     # read back, do not assume
        assert back["lines"] == doc["lines"], lang
        assert back["intention"], f"{lang}: the pack had no intention line"
        print(f"  wrote {where.relative_to(ROOT)}")
    print("\n  Now run tools/retext_salaah_quran.py --write to give Portuguese its "
          "Qur'an from Helmi Nasr.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
