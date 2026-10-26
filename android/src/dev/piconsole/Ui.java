// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

final class Ui {
    static final int BG = Color.rgb(11, 23, 39);
    static final int CARD = Color.rgb(20, 39, 57);
    static final int TEXT = Color.rgb(232, 246, 247);
    static final int MUTED = Color.rgb(153, 180, 188);
    static final int TEAL = Color.rgb(70, 214, 204);

    static int dp(Context c, int value) { return (int) (value * c.getResources().getDisplayMetrics().density + 0.5f); }

    static LinearLayout column(Context c) {
        LinearLayout layout = new LinearLayout(c);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    static TextView text(Context c, String value, int sp, int color, boolean bold) {
        TextView view = new TextView(c);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    static GradientDrawable background(int color, Context c, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(c, radius));
        return drawable;
    }

    static LinearLayout card(Context c) {
        LinearLayout card = column(c);
        card.setPadding(dp(c, 16), dp(c, 14), dp(c, 16), dp(c, 14));
        card.setBackground(background(CARD, c, 18));
        LinearLayout.LayoutParams margin = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        margin.bottomMargin = dp(c, 10);
        card.setLayoutParams(margin);
        return card;
    }

    static void add(LinearLayout parent, View child) {
        if (child.getLayoutParams() == null) child.setLayoutParams(new LinearLayout.LayoutParams(-1, -2));
        parent.addView(child);
    }
}
